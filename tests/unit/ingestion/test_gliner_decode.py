"""Tests for decode_gliner, the reader of gliner2 output.

Raw dicts here have the shape that gliner2 returns for
``include_confidence=True, include_spans=True``. The tests cover: the label
choice when one span returns under several labels, native offsets and their
whitespace trim, the relation cut and the pattern check, endpoints that match
no kept span, the entity band, and the candidate switch.
"""

import hashlib
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion._gliner_decode import decode_gliner
from agrag.ingestion.settings import ExtractionSettings


_TEXT = "Ada Lovelace works at Acme Corp. Acme Corp supplies Bolt Ltd."

_SCHEMA = GraphSchema(
    name="vendors",
    version="1",
    entities=[
        EntityType(label="Person", description="A named individual."),
        EntityType(label="Organization", description="A company or institution."),
        EntityType(
            label="Vendor",
            description="An organization that sells goods.",
            parents=["Organization"],
        ),
        EntityType(
            label="Contract",
            description="A signed agreement.",
            properties={"term": PropertySpec(type="string")},
        ),
    ],
    relations=[
        RelationType(
            label="WORKS_AT",
            description="A person works at an organization.",
            patterns=[("Person", "Organization")],
        ),
        RelationType(
            label="SUPPLIES",
            description="A vendor supplies an organization.",
            patterns=[("Vendor", "Organization")],
        ),
    ],
)


def _hit(needle: str, confidence: float, nth: int = 0) -> dict[str, Any]:
    """Return the gliner2 span dict for the nth occurrence of needle."""
    start = -1
    for _ in range(nth + 1):
        start = _TEXT.index(needle, start + 1)
    return {
        "text": needle,
        "confidence": confidence,
        "start": start,
        "end": start + len(needle),
    }


def _edge(head: dict[str, Any], tail: dict[str, Any], score: float) -> dict[str, Any]:
    """Return the gliner2 relation dict for two spans at one relation score."""
    return {
        "head": {**head, "confidence": score},
        "tail": {**tail, "confidence": score},
    }


def _decode(
    raw: dict[str, Any],
    *,
    band: dict[str, Any] | None = None,
    settings: ExtractionSettings | None = None,
) -> ExtractionResult:
    """Decode raw gliner2 output for the fixed chunk text."""
    chunk = Chunk(
        id=uuid4(),
        document_id=uuid4(),
        text=_TEXT,
        content_hash=hashlib.sha256(_TEXT.encode("utf-8")).hexdigest(),
        provenance=TextProvenance(char_start=0, char_end=len(_TEXT)),
    )
    return decode_gliner(raw, band, chunk, _SCHEMA, settings or ExtractionSettings())


class TestDecodeGliner:
    """decode_gliner turns one gliner2 result into mentions and candidates."""

    def test_entities_carry_native_offsets_and_confidence(self) -> None:
        """Offsets and scores come from gliner2 and entities follow text order."""
        raw = {
            "entities": {
                "Organization": [_hit("Acme Corp", 0.81)],
                "Person": [_hit("Ada Lovelace", 0.93)],
            },
            "relation_extraction": {},
        }

        result = _decode(raw)

        assert [
            (e.label, e.text, e.char_start, e.char_end, e.confidence)
            for e in result.entities
        ] == [
            ("Person", "Ada Lovelace", 0, 12, 0.93),
            ("Organization", "Acme Corp", 22, 31, 0.81),
        ]
        assert result.extractor_name == "gliner"

    @pytest.mark.parametrize(
        ("organization", "vendor", "expected"),
        [(0.6, 0.8, "Vendor"), (0.9, 0.7, "Organization"), (0.8, 0.8, "Vendor")],
    )
    def test_keeps_the_highest_scoring_label_for_one_span(
        self, organization: float, vendor: float, expected: str
    ) -> None:
        """A span returned under a parent and a child keeps one label.

        On a tie the deeper (child) label wins.
        """
        raw = {
            "entities": {
                "Organization": [_hit("Acme Corp", organization)],
                "Vendor": [_hit("Acme Corp", vendor)],
            }
        }

        result = _decode(raw)

        assert [(e.label, e.confidence) for e in result.entities] == [
            (expected, max(organization, vendor))
        ]

    def test_offsets_exclude_whitespace_around_the_text(self) -> None:
        """gliner2 strips the text but not the range, so the range is trimmed."""
        padded = _hit("Acme Corp", 0.8)
        padded["start"] -= 1
        raw = {"entities": {"Organization": [padded]}}

        (entity,) = _decode(raw).entities

        assert (entity.char_start, entity.char_end) == (22, 31)
        assert _TEXT[entity.char_start : entity.char_end] == entity.text

    @pytest.mark.parametrize(
        "span", [(-1, 3), (5, 5), (60, 99)], ids=["negative", "empty", "past-end"]
    )
    def test_skips_a_span_outside_the_chunk(self, span: tuple[int, int]) -> None:
        """A malformed range is dropped instead of raising."""
        raw = {
            "entities": {
                "Person": [
                    {"text": "x", "confidence": 0.9, "start": span[0], "end": span[1]}
                ]
            }
        }

        assert _decode(raw).entities == []

    def test_relation_at_the_cut_is_kept_with_its_confidence(self) -> None:
        """A relation scoring exactly the relation threshold is kept."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        raw = {
            "entities": {"Person": [ada], "Organization": [acme]},
            "relation_extraction": {"WORKS_AT": [_edge(ada, acme, 0.7)]},
        }

        result = _decode(raw)

        (relation,) = result.relations
        assert (relation.label, relation.source_index, relation.target_index) == (
            "WORKS_AT",
            0,
            1,
        )
        assert relation.confidence == 0.7
        assert result.candidates == []

    def test_relation_below_the_cut_becomes_a_candidate(self) -> None:
        """A relation under 0.7 is not kept and is returned as a candidate."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        raw = {
            "entities": {"Person": [ada], "Organization": [acme]},
            "relation_extraction": {"WORKS_AT": [_edge(ada, acme, 0.55)]},
        }

        result = _decode(raw)

        assert result.relations == []
        (candidate,) = result.candidates
        assert candidate.kind == "relation"
        assert candidate.reason == "below_relation_cut"
        assert candidate.label == "WORKS_AT"
        assert (candidate.source_text, candidate.target_text) == (
            "Ada Lovelace",
            "Acme Corp",
        )
        assert candidate.confidence == 0.55

    def test_relation_drop_is_counted_when_candidate_writing_is_disabled(self) -> None:
        """Relation discards remain visible when candidate records are off."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        raw = {
            "entities": {"Person": [ada], "Organization": [acme]},
            "relation_extraction": {"WORKS_AT": [_edge(acme, ada, 0.9)]},
        }

        result = _decode(raw, settings=ExtractionSettings(candidates_enabled=False))

        assert result.candidates == []
        assert [
            (item.kind, item.label, item.reason, item.count) for item in result.dropped
        ] == [("relation", "WORKS_AT", "off_pattern", 1)]

    def test_endpoint_without_a_kept_span_becomes_a_candidate(self) -> None:
        """A relation whose tail is not a kept entity keeps its endpoint text."""
        ada, bolt = _hit("Ada Lovelace", 0.9), _hit("Bolt Ltd", 0.9)
        raw = {
            "entities": {"Person": [ada]},
            "relation_extraction": {"WORKS_AT": [_edge(ada, bolt, 0.8)]},
        }

        result = _decode(raw)

        assert result.relations == []
        (candidate,) = result.candidates
        assert candidate.reason == "unresolved_endpoint"
        assert candidate.target_text == "Bolt Ltd"
        assert candidate.source_label == "Person"
        assert candidate.target_label is None

    def test_relation_off_pattern_becomes_a_candidate(self) -> None:
        """A relation whose endpoint labels fit no pattern is a candidate."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        raw = {
            "entities": {"Person": [ada], "Organization": [acme]},
            "relation_extraction": {"WORKS_AT": [_edge(acme, ada, 0.9)]},
        }

        result = _decode(raw)

        assert result.relations == []
        (candidate,) = result.candidates
        assert candidate.reason == "off_pattern"
        assert candidate.source_text == "Acme Corp"

    def test_pattern_check_accepts_a_child_of_the_pattern_label(self) -> None:
        """WORKS_AT names Organization, and a Vendor endpoint satisfies it."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        raw = {
            "entities": {"Person": [ada], "Vendor": [acme]},
            "relation_extraction": {"WORKS_AT": [_edge(ada, acme, 0.9)]},
        }

        result = _decode(raw)

        assert [r.label for r in result.relations] == ["WORKS_AT"]

    def test_relation_between_one_entity_and_itself_is_dropped(self) -> None:
        """A self relation is neither kept nor a candidate."""
        ada = _hit("Ada Lovelace", 0.9)
        raw = {
            "entities": {"Person": [ada]},
            "relation_extraction": {"WORKS_AT": [_edge(ada, ada, 0.9)]},
        }

        result = _decode(raw)

        assert result.relations == []
        assert result.candidates == []

    def test_endpoint_matches_by_unique_text_when_offsets_differ(self) -> None:
        """An endpoint with shifted offsets still binds when its text is unique."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        shifted = {**ada, "start": 1, "end": 13}
        raw = {
            "entities": {"Person": [ada], "Organization": [acme]},
            "relation_extraction": {"WORKS_AT": [_edge(shifted, acme, 0.9)]},
        }

        result = _decode(raw)

        assert [(r.source_index, r.target_index) for r in result.relations] == [(0, 1)]

    def test_repeated_relation_keeps_the_higher_confidence(self) -> None:
        """Two edges between the same entities and label give one relation."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        raw = {
            "entities": {"Person": [ada], "Organization": [acme]},
            "relation_extraction": {
                "WORKS_AT": [_edge(ada, acme, 0.75), _edge(ada, acme, 0.9)]
            },
        }

        (relation,) = _decode(raw).relations

        assert relation.confidence == 0.9

    def test_label_threshold_replaces_the_relation_cut(self) -> None:
        """A per-label threshold moves the cut for that relation only."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        raw = {
            "entities": {"Person": [ada], "Organization": [acme]},
            "relation_extraction": {"WORKS_AT": [_edge(ada, acme, 0.8)]},
        }
        settings = ExtractionSettings(label_thresholds={"WORKS_AT": 0.9})

        result = _decode(raw, settings=settings)

        assert result.relations == []
        assert [c.reason for c in result.candidates] == ["below_relation_cut"]

    def test_unshared_band_span_becomes_an_entity_candidate(self) -> None:
        """A 0.3 to 0.5 span away from every kept span is an entity candidate."""
        raw = {"entities": {"Person": [_hit("Ada Lovelace", 0.9)]}}
        band = {"entities": {"Organization": [_hit("Bolt Ltd", 0.4)]}}

        result = _decode(raw, band=band)

        (candidate,) = result.candidates
        assert (candidate.kind, candidate.reason) == ("entity", "entity_band")
        assert (candidate.label, candidate.text, candidate.confidence) == (
            "Organization",
            "Bolt Ltd",
            0.4,
        )

    @pytest.mark.parametrize(
        ("needle", "confidence"),
        [("Ada", 0.4), ("Bolt Ltd", 0.5), ("Bolt Ltd", 0.2)],
        ids=["overlaps-kept-span", "at-entity-threshold", "below-band-floor"],
    )
    def test_band_span_outside_the_band_is_not_a_candidate(
        self, needle: str, confidence: float
    ) -> None:
        """Overlap with a kept span, or a score outside the band, gives nothing."""
        raw = {"entities": {"Person": [_hit("Ada Lovelace", 0.9)]}}
        band = {"entities": {"Organization": [_hit(needle, confidence)]}}

        assert _decode(raw, band=band).candidates == []

    def test_no_candidates_when_candidates_are_off(self) -> None:
        """The switch removes relation and band candidates alike."""
        ada, acme = _hit("Ada Lovelace", 0.9), _hit("Acme Corp", 0.9)
        raw = {
            "entities": {"Person": [ada], "Organization": [acme]},
            "relation_extraction": {"WORKS_AT": [_edge(ada, acme, 0.4)]},
        }
        band = {"entities": {"Organization": [_hit("Bolt Ltd", 0.4)]}}

        result = _decode(
            raw, band=band, settings=ExtractionSettings(candidates_enabled=False)
        )

        assert result.candidates == []

    @pytest.mark.parametrize(
        ("label", "expected"),
        [("Contract", True), ("Person", False)],
    )
    def test_needs_properties_follows_the_kept_entity_types(
        self, label: str, expected: bool
    ) -> None:
        """The flag is true only when a kept entity type declares properties."""
        raw = {"entities": {label: [_hit("Ada Lovelace", 0.9)]}}

        assert _decode(raw).needs_properties is expected

    def test_empty_output_gives_an_empty_result(self) -> None:
        """No entities and no relations decode to an empty result."""
        result = _decode({})

        assert result.entities == []
        assert result.relations == []
        assert result.candidates == []
        assert result.needs_properties is False
