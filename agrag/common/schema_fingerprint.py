"""Fingerprints of a schema and of the extraction setup that ran against it.

``schema_fingerprint`` covers structure. ``extraction_fingerprint`` covers what
the extractor reads besides structure: descriptions, the settings that change
its output, and the model name. ``Graph`` stores both on every document and
chunk it writes, and ``update()`` compares them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict

from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.common.fingerprint import fingerprint_of


if TYPE_CHECKING:
    from agrag.ingestion.settings import ExtractionSettings


# ExtractionSettings fields that are not hashed as settings. The budget picks
# the weakest chunks of one walk batch, so its effect depends on the other
# documents in the batch and a per-document hash cannot describe it. The mode
# is replaced by the effective mode, which the caller passes in.
_UNTRACKED_SETTINGS = frozenset({"escalation_budget", "mode"})
# Read only by the hybrid tier. Outside hybrid it changes no output.
_HYBRID_ONLY_SETTINGS = frozenset({"escalation_threshold"})


def _property_structure(spec: PropertySpec) -> dict[str, object]:
    data = spec.model_dump(mode="json", exclude={"description"})
    if data["enum"] is not None:
        data["enum"] = sorted(data["enum"])
    return data


def _entity_structure(entity: EntityType) -> dict[str, object]:
    # Parents are a set of stored labels, so their order does not matter.
    data = entity.model_dump(mode="json", exclude={"description", "properties"})
    data["parents"] = sorted(data["parents"])
    data["properties"] = {
        name: _property_structure(spec) for name, spec in entity.properties.items()
    }
    return data


def _relation_structure(relation: RelationType) -> dict[str, object]:
    data = relation.model_dump(mode="json", exclude={"description"})
    data["patterns"] = sorted(data["patterns"])
    return data


def schema_fingerprint(schema: GraphSchema) -> str:
    """Return the hash of the structure of a schema.

    The hash covers entity types, parents, properties (type, required, enum),
    relations, patterns, cardinality and symmetry. It ignores every description,
    the schema name and the schema version, and the order of entities, relations,
    patterns, parents and enum values.

    Args:
        schema: The schema to hash.

    Returns:
        The first 16 hex characters of the SHA-256 of the canonical structure.
    """
    entities = sorted(
        (_entity_structure(entity) for entity in schema.entities),
        key=lambda data: str(data["label"]),
    )
    relations = sorted(
        (_relation_structure(relation) for relation in schema.relations),
        key=lambda data: str(data["label"]),
    )
    return fingerprint_of({"entities": entities, "relations": relations})


class LLMOutputSettings(TypedDict):
    """Extractor options that change LLM output besides the model and prompt.

    Attributes:
        include_heading_path: Whether the chunk's heading path is sent to the
            model as context.
    """

    include_heading_path: bool


def extraction_fingerprint(
    schema: GraphSchema,
    settings: ExtractionSettings,
    *,
    effective_mode: Literal["gliner", "hybrid", "llm"],
    llm_model: str | None,
    prompt_id: str | None,
    llm_output: LLMOutputSettings | None = None,
) -> str:
    """Return the hash of everything the extractor reads besides structure.

    The hash covers the entity, relation and property descriptions, the
    ``ExtractionSettings`` fields except ``escalation_budget`` and ``mode``, and
    the effective mode. ``escalation_threshold`` is hashed only for ``hybrid``.
    The LLM model name, prompt identity and LLM output options are hashed only
    when the effective mode is ``hybrid`` or ``llm``. A new settings field is
    included until it is added to the exclude list.

    Args:
        schema: The schema whose descriptions the extractor reads.
        settings: The extraction settings of the run.
        effective_mode: The mode the run uses after the degrade rule.
        llm_model: The model name of the LLM slot, or None without an LLM.
        prompt_id: The prompt identity of the LLM tier, or None without an LLM.
        llm_output: The output options of the LLM slot, or None when the slot
            has none to report.

    Returns:
        The first 16 hex characters of the SHA-256 of the canonical data.
    """
    descriptions = {
        "entities": {
            entity.label: {
                "description": entity.description,
                "properties": {
                    name: spec.description for name, spec in entity.properties.items()
                },
            }
            for entity in schema.entities
        },
        "relations": {
            relation.label: relation.description for relation in schema.relations
        },
    }
    excluded = set(_UNTRACKED_SETTINGS)
    if effective_mode != "hybrid":
        excluded |= _HYBRID_ONLY_SETTINGS
    tracked = settings.model_dump(mode="json", exclude=excluded)
    llm: dict[str, object] | None = None
    if effective_mode != "gliner":
        llm = {"model": llm_model, "prompt": prompt_id, "output": llm_output}
    return fingerprint_of(
        {
            "descriptions": descriptions,
            "settings": tracked,
            "effective_mode": effective_mode,
            "llm": llm,
        }
    )


@dataclass(frozen=True, slots=True)
class RunRecord:
    """What a document and its chunks record about the run that wrote them.

    Attributes:
        schema_name: The name of the schema of the run.
        schema_version: The version string of the schema of the run.
        schema_fingerprint: The structure hash of the schema.
        extraction_fingerprint: The hash of descriptions, settings, effective
            mode and LLM inputs.
    """

    schema_name: str
    schema_version: str
    schema_fingerprint: str
    extraction_fingerprint: str

    def stamp(self, document: Document) -> Document:
        """Return a copy of a document that carries this record.

        Args:
            document: The document to stamp. It is not changed.

        Returns:
            A copy with the four run-record fields set.
        """
        return document.model_copy(
            update={
                "schema_name": self.schema_name,
                "schema_version": self.schema_version,
                "schema_fingerprint": self.schema_fingerprint,
                "extraction_fingerprint": self.extraction_fingerprint,
            }
        )


def run_record(
    schema: GraphSchema,
    settings: ExtractionSettings,
    *,
    effective_mode: Literal["gliner", "hybrid", "llm"],
    llm_model: str | None,
    prompt_id: str | None,
    llm_output: LLMOutputSettings | None = None,
) -> RunRecord:
    """Build the run record of a schema and a set of extraction settings.

    Args:
        schema: The schema of the run.
        settings: The extraction settings of the run.
        effective_mode: The mode the run uses after the degrade rule.
        llm_model: The model name of the LLM slot, or None without an LLM.
        prompt_id: The prompt identity of the LLM tier, or None without an LLM.
        llm_output: The output options of the LLM slot, or None when the slot
            has none to report.

    Returns:
        The record with name, version and both fingerprints.
    """
    return RunRecord(
        schema_name=schema.name,
        schema_version=schema.version,
        schema_fingerprint=schema_fingerprint(schema),
        extraction_fingerprint=extraction_fingerprint(
            schema,
            settings,
            effective_mode=effective_mode,
            llm_model=llm_model,
            prompt_id=prompt_id,
            llm_output=llm_output,
        ),
    )
