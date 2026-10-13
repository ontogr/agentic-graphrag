"""Tests for the schema and extraction fingerprints and the run record.

Covers which schema edits change the structure hash, which edits change the
extraction hash, which ExtractionSettings fields each effective mode tracks,
and how a run record stamps a document.
"""

import re
import subprocess
import sys
from collections.abc import Callable
from typing import Any, Literal

import pytest

from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.schema_fingerprint import (
    extraction_fingerprint,
    run_record,
    schema_fingerprint,
)
from agrag.ingestion.settings import ExtractionSettings


_HEX_16 = re.compile(r"[0-9a-f]{16}")

EffectiveMode = Literal["gliner", "hybrid", "llm"]

_CHANGED: dict[str, Any] = {
    "model_name": "other/model",
    "dtype": "fp16",
    "entity_threshold": 0.6,
    "relation_threshold": 0.8,
    "relation_floor": 0.2,
    "band_floor": 0.2,
    "label_thresholds": {"Person": 0.9},
    "escalation_threshold": 0.5,
    "escalation_budget": 0.5,
    "min_escalation_words": 3,
    "candidates_enabled": False,
    "mode": "llm",
}

_ALWAYS_TRACKED = frozenset(
    {
        "model_name",
        "dtype",
        "entity_threshold",
        "relation_threshold",
        "relation_floor",
        "band_floor",
        "label_thresholds",
        "min_escalation_words",
        "candidates_enabled",
    }
)


def _entity(data: dict[str, Any], label: str) -> dict[str, Any]:
    return next(entity for entity in data["entities"] if entity["label"] == label)


def _relation(data: dict[str, Any], label: str) -> dict[str, Any]:
    return next(
        relation for relation in data["relations"] if relation["label"] == label
    )


def _schema(*, name: str = "people", version: str = "1") -> GraphSchema:
    return GraphSchema(
        name=name,
        version=version,
        entities=[
            EntityType(label="Agent", description="An actor."),
            EntityType(
                label="Organization",
                description="A company.",
            ),
            EntityType(
                label="Person",
                description="A human.",
                parents=["Agent", "Organization"],
                properties={
                    "role": {
                        "type": "string",
                        "required": True,
                        "enum": ["lead", "staff"],
                        "description": "Job role.",
                    }
                },
            ),
        ],
        relations=[
            {
                "label": "WORKS_FOR",
                "description": "Employment.",
                "patterns": [["Person", "Organization"], ["Organization", "Person"]],
                "cardinality": {"max_per_source": 1},
            },
            {
                "label": "FOUNDED",
                "description": "Founding.",
                "patterns": [["Person", "Organization"]],
            },
        ],
    )


def _variant(mutate: Callable[[dict[str, Any]], None]) -> GraphSchema:
    data = _schema().model_dump(mode="json")
    mutate(data)
    return GraphSchema.model_validate(data)


def _fingerprint(
    *,
    schema: GraphSchema | None = None,
    settings: ExtractionSettings | None = None,
    mode: EffectiveMode,
    llm_model: str | None = "model-a",
    prompt_id: str | None = "prompt-a",
) -> str:
    return extraction_fingerprint(
        schema if schema is not None else _schema(),
        settings if settings is not None else ExtractionSettings(),
        effective_mode=mode,
        llm_model=llm_model,
        prompt_id=prompt_id,
    )


_DESCRIPTION_EDITS = [
    pytest.param(
        lambda d: _entity(d, "Person").update(description="Changed."),
        id="entity-description",
    ),
    pytest.param(
        lambda d: _relation(d, "WORKS_FOR").update(description="Changed."),
        id="relation-description",
    ),
    pytest.param(
        lambda d: _entity(d, "Person")["properties"]["role"].update(
            description="Changed."
        ),
        id="property-description",
    ),
]

_REORDERINGS = [
    pytest.param(lambda d: d["entities"].reverse(), id="entities"),
    pytest.param(lambda d: d["relations"].reverse(), id="relations"),
    pytest.param(lambda d: _entity(d, "Person")["parents"].reverse(), id="parents"),
    pytest.param(
        lambda d: _entity(d, "Person")["properties"]["role"]["enum"].reverse(),
        id="enum",
    ),
    pytest.param(
        lambda d: _relation(d, "WORKS_FOR")["patterns"].reverse(), id="patterns"
    ),
]

_STRUCTURAL_EDITS = [
    pytest.param(
        lambda d: _entity(d, "Person").update(parents=["Organization"]),
        id="parents",
    ),
    pytest.param(
        lambda d: _entity(d, "Person")["properties"]["role"].update(
            enum=["lead", "staff", "intern"]
        ),
        id="enum",
    ),
    pytest.param(
        lambda d: _entity(d, "Person")["properties"]["role"].update(required=False),
        id="required",
    ),
    pytest.param(
        lambda d: _relation(d, "WORKS_FOR")["cardinality"].update(max_per_source=2),
        id="cardinality",
    ),
    pytest.param(
        lambda d: _relation(d, "FOUNDED").update(symmetric=True),
        id="symmetric",
    ),
    pytest.param(
        lambda d: d["entities"].append(
            {"label": "Place", "description": "A location.", "parents": []}
        ),
        id="added-entity",
    ),
    pytest.param(
        lambda d: _relation(d, "FOUNDED")["patterns"].append(["Person", "Person"]),
        id="pattern",
    ),
    pytest.param(
        lambda d: _entity(d, "Person")["properties"].update(
            {"description": {"type": "string"}}
        ),
        id="property-named-description",
    ),
]


class TestSchemaFingerprint:
    """schema_fingerprint hashes structure and nothing else."""

    def test_returns_sixteen_lowercase_hex_characters_stable_across_calls(
        self,
    ) -> None:
        """The same schema always hashes to the same 16-hex value."""
        first = schema_fingerprint(_schema())

        assert _HEX_16.fullmatch(first)
        assert schema_fingerprint(_schema()) == first

    @pytest.mark.parametrize("reorder", _REORDERINGS)
    def test_ignores_order_of_entities_relations_patterns_parents_and_enum(
        self, reorder: Callable[[dict[str, Any]], None]
    ) -> None:
        """Reordering lists that are sets in meaning leaves the hash unchanged."""
        assert schema_fingerprint(_variant(reorder)) == schema_fingerprint(_schema())

    @pytest.mark.parametrize("edit", _DESCRIPTION_EDITS)
    def test_ignores_descriptions(self, edit: Callable[[dict[str, Any]], None]) -> None:
        """Descriptions are guidance for the extractor, not structure."""
        assert schema_fingerprint(_variant(edit)) == schema_fingerprint(_schema())

    def test_ignores_name_and_version(self) -> None:
        """A renamed or re-versioned schema with the same types keeps its hash."""
        renamed = _schema(name="renamed", version="2")

        assert schema_fingerprint(renamed) == schema_fingerprint(_schema())

    @pytest.mark.parametrize("edit", _STRUCTURAL_EDITS)
    def test_changes_for_every_structural_edit(
        self, edit: Callable[[dict[str, Any]], None]
    ) -> None:
        """Each structural edit produces a different hash."""
        assert schema_fingerprint(_variant(edit)) != schema_fingerprint(_schema())


class TestExtractionFingerprint:
    """extraction_fingerprint covers descriptions and the extraction setup."""

    def test_returns_sixteen_lowercase_hex_characters(self) -> None:
        """The hash has the same shape as the structure hash."""
        assert _HEX_16.fullmatch(_fingerprint(mode="hybrid"))

    @pytest.mark.parametrize("edit", _DESCRIPTION_EDITS)
    def test_changes_for_every_description_edit(
        self, edit: Callable[[dict[str, Any]], None]
    ) -> None:
        """The extractor reads descriptions, so a description edit re-extracts."""
        changed = _fingerprint(schema=_variant(edit), mode="hybrid")

        assert changed != _fingerprint(mode="hybrid")

    def test_ignores_name_and_version(self) -> None:
        """A renamed or re-versioned schema with the same text keeps its hash."""
        renamed = _schema(name="renamed", version="2")

        assert _fingerprint(schema=renamed, mode="hybrid") == _fingerprint(
            mode="hybrid"
        )

    @pytest.mark.parametrize(
        ("mode", "expected_changed"),
        [
            pytest.param(
                "gliner",
                _ALWAYS_TRACKED,
                id="gliner",
            ),
            pytest.param(
                "hybrid",
                _ALWAYS_TRACKED | {"escalation_threshold"},
                id="hybrid",
            ),
            pytest.param(
                "llm",
                _ALWAYS_TRACKED,
                id="llm",
            ),
        ],
    )
    def test_only_the_expected_settings_change_the_fingerprint(
        self, mode: EffectiveMode, expected_changed: frozenset[str]
    ) -> None:
        """Each effective mode tracks a fixed set of settings fields.

        A new settings field makes the coverage check below fail until it is
        added to the tracked or untracked lists in the module.
        """
        baseline = _fingerprint(mode=mode)

        changed = {
            name
            for name, value in _CHANGED.items()
            if _fingerprint(
                settings=ExtractionSettings().model_copy(update={name: value}),
                mode=mode,
            )
            != baseline
        }

        assert set(_CHANGED) == set(ExtractionSettings.model_fields)
        assert changed == expected_changed

    @pytest.mark.parametrize(
        ("mode", "expected_changed"),
        [
            pytest.param("gliner", False, id="gliner"),
            pytest.param("hybrid", True, id="hybrid"),
            pytest.param("llm", True, id="llm"),
        ],
    )
    def test_llm_inputs_matter_only_when_an_llm_runs(
        self, mode: EffectiveMode, expected_changed: bool
    ) -> None:
        """The LLM model and prompt only affect runs that call the LLM."""
        baseline = _fingerprint(mode=mode)

        other_model = _fingerprint(mode=mode, llm_model="model-b")
        other_prompt = _fingerprint(mode=mode, prompt_id="prompt-b")

        assert (other_model != baseline) is expected_changed
        assert (other_prompt != baseline) is expected_changed

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            pytest.param("gliner", "hybrid", id="gliner-vs-hybrid"),
            pytest.param("hybrid", "llm", id="hybrid-vs-llm"),
            pytest.param("gliner", "llm", id="gliner-vs-llm"),
        ],
    )
    def test_effective_mode_changes_the_fingerprint(
        self, first: EffectiveMode, second: EffectiveMode
    ) -> None:
        """A run in a different effective mode never matches the old fingerprint."""
        assert _fingerprint(mode=first) != _fingerprint(mode=second)

    def test_label_threshold_key_order_is_ignored(self) -> None:
        """The same thresholds in another insertion order hash the same."""
        forward = ExtractionSettings(
            label_thresholds={"Person": 0.9, "Organization": 0.8}
        )
        backward = ExtractionSettings(
            label_thresholds={"Organization": 0.8, "Person": 0.9}
        )

        assert _fingerprint(settings=forward, mode="hybrid") == _fingerprint(
            settings=backward, mode="hybrid"
        )


class TestRunRecord:
    """run_record carries the schema identity and both fingerprints."""

    def test_records_schema_name_and_version(self) -> None:
        """The record names the schema and its version as the run saw them."""
        record = run_record(
            _schema(name="people", version="3"),
            ExtractionSettings(),
            effective_mode="gliner",
            llm_model=None,
            prompt_id=None,
        )

        assert record.schema_name == "people"
        assert record.schema_version == "3"

    def test_stamp_returns_a_copy_and_leaves_the_document_unchanged(self) -> None:
        """Stamping sets the four fields on a copy and never mutates the input."""
        document = Document(
            text="hello world",
            title="t",
            uri="u",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="h",
            loader_name="text",
            char_count=11,
        )
        before = document.model_dump()
        record = run_record(
            _schema(name="people", version="3"),
            ExtractionSettings(),
            effective_mode="gliner",
            llm_model=None,
            prompt_id=None,
        )

        stamped = record.stamp(document)

        assert stamped is not document
        assert document.model_dump() == before
        assert stamped.schema_name == "people"
        assert stamped.schema_version == "3"
        assert stamped.schema_fingerprint == record.schema_fingerprint
        assert stamped.extraction_fingerprint == record.extraction_fingerprint


def test_module_imports_in_a_fresh_interpreter() -> None:
    """The module imports without first importing the ingestion package."""
    subprocess.run(
        [sys.executable, "-c", "import agrag.common.schema_fingerprint"],
        check=True,
    )
