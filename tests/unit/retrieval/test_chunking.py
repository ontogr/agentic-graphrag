"""Tests for chunk node detection and parsing in agrag.retrieval.chunking.

A node value is a Chunk when a driver node carries the Chunk label, or when a
property dict holds the fields only a Chunk node stores. A malformed Chunk
node is skipped with a warning that names its id, and never raises.
"""

import json
import logging
from dataclasses import dataclass
from uuid import UUID

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.retrieval.chunking import is_chunk_node, parse_chunk_node


CHUNK_ID = "7d1c1f5e-8f0a-4b7e-9c5a-2d3e4f5a6b7c"
DOCUMENT_ID = "3c2b1a09-8e7d-4c6b-a5f4-e3d2c1b0a998"
TEXT_PROVENANCE = json.dumps({"kind": "text", "char_start": 0, "char_end": 5})


@dataclass
class _DriverNode:
    """A stand-in for a driver node that exposes its labels."""

    labels: frozenset[str]


def _chunk_properties(**overrides: object) -> dict[str, object]:
    properties: dict[str, object] = {
        "id": CHUNK_ID,
        "document_id": DOCUMENT_ID,
        "index": 0,
        "text": "hello",
        "provenance": TEXT_PROVENANCE,
        "heading_path": [],
        "content_kind": "text",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    properties.update(overrides)
    return properties


class TestIsChunkNode:
    """A node value is a Chunk by its label, or by its chunk-only fields."""

    def test_driver_node_with_chunk_label_is_a_chunk(self) -> None:
        """A node labelled Chunk is a chunk node."""
        assert is_chunk_node(_DriverNode(labels=frozenset({"Chunk"})))

    def test_driver_node_with_other_labels_is_not_a_chunk(self) -> None:
        """A node without the Chunk label is not a chunk node."""
        assert not is_chunk_node(_DriverNode(labels=frozenset({"Entity"})))

    def test_property_dict_with_chunk_only_fields_is_a_chunk(self) -> None:
        """A flat property dict with document_id and provenance is a chunk node."""
        assert is_chunk_node(_chunk_properties())

    def test_property_dict_without_chunk_only_fields_is_not_a_chunk(self) -> None:
        """A dict missing document_id or provenance is not a chunk node."""
        assert not is_chunk_node({"id": CHUNK_ID, "name": "Ada"})

    @pytest.mark.parametrize("value", [None, "Chunk", 5, ["Chunk"]])
    def test_other_values_are_not_chunks(self, value: object) -> None:
        """Values that are neither a labelled node nor a mapping are not chunks."""
        assert not is_chunk_node(value)


class TestParseChunkNode:
    """A well-formed node parses to a Chunk. A malformed one is skipped."""

    def test_well_formed_node_parses_to_chunk(self) -> None:
        """A valid property dict yields its Chunk."""
        chunk = parse_chunk_node(_chunk_properties())

        assert isinstance(chunk, Chunk)
        assert chunk.id == UUID(CHUNK_ID)
        assert chunk.text == "hello"

    def test_node_wrapper_with_properties_key_parses_to_chunk(self) -> None:
        """A dict that nests its values under ``properties`` parses to a Chunk."""
        chunk = parse_chunk_node({"id": CHUNK_ID, "properties": _chunk_properties()})

        assert isinstance(chunk, Chunk)

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param(None, id="none"),
            pytest.param("chunk", id="string"),
            pytest.param(5, id="int"),
            pytest.param([1, 2], id="list"),
            pytest.param({}, id="empty_dict"),
        ],
    )
    def test_value_without_properties_returns_none(self, value: object) -> None:
        """A value that holds no properties is not a chunk."""
        assert parse_chunk_node(value) is None

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"section_ids": 5}, id="section_ids_int"),
            pytest.param({"section_ids": "abc"}, id="section_ids_string"),
            pytest.param({"section_ids": {"a": 1}}, id="section_ids_dict"),
            pytest.param({"section_ids": [[1, 2]]}, id="section_ids_nested_list"),
            pytest.param(
                {"section_ids": [CHUNK_ID, CHUNK_ID]}, id="section_ids_repeated"
            ),
            pytest.param({"provenance": 5}, id="provenance_int"),
            pytest.param({"provenance": [1, 2]}, id="provenance_list"),
            pytest.param({"provenance": None}, id="provenance_none"),
            pytest.param({"provenance": b"{}"}, id="provenance_bytes"),
            pytest.param({"provenance": {1, 2}}, id="provenance_set"),
            pytest.param({"provenance": "{not json"}, id="provenance_bad_json"),
            pytest.param({"provenance": "[1, 2]"}, id="provenance_json_list"),
            pytest.param({"provenance": "null"}, id="provenance_json_null"),
            pytest.param(
                {"provenance": json.dumps({"kind": ["text"]})},
                id="provenance_unhashable_kind",
            ),
            pytest.param(
                {"provenance": json.dumps({"kind": "other"})},
                id="provenance_unknown_kind",
            ),
            pytest.param(
                {"provenance": json.dumps({"kind": "text", "char_start": 1.5})},
                id="provenance_fractional_offset",
            ),
            pytest.param(
                {"provenance": "[" * 100_000 + "]" * 100_000},
                id="provenance_deep_nesting",
            ),
            pytest.param({"heading_path": 3}, id="heading_path_int"),
            pytest.param({"heading_path": "abc"}, id="heading_path_string"),
            pytest.param({"heading_path": [{"a": 1}]}, id="heading_path_dict_item"),
            pytest.param({"heading_path": ["   "]}, id="heading_path_blank"),
            pytest.param({"embedding": "abc"}, id="embedding_string"),
            pytest.param({"embedding": {"a": 1}}, id="embedding_dict"),
            pytest.param({"index": [1]}, id="index_list"),
            pytest.param({"index": None}, id="index_none"),
            pytest.param({"text": ["a"]}, id="text_list"),
            pytest.param({"text": None}, id="text_none"),
            pytest.param({"content_kind": ["table"]}, id="content_kind_list"),
            pytest.param({"created_at": [1]}, id="created_at_list"),
            pytest.param({"created_at": object()}, id="created_at_object"),
            pytest.param({"document_id": None}, id="document_id_none"),
            pytest.param({"chunker": ["x"]}, id="chunker_list"),
        ],
    )
    def test_malformed_chunk_returns_none_and_warns_with_chunk_id(
        self, overrides: dict[str, object], caplog: pytest.LogCaptureFixture
    ) -> None:
        """A chunk whose field has the wrong shape is skipped with its id logged."""
        caplog.set_level(logging.WARNING, logger="agrag.retrieval.chunking")

        assert parse_chunk_node(_chunk_properties(**overrides)) is None

        warnings = [
            record for record in caplog.records if record.levelno == logging.WARNING
        ]
        assert len(warnings) == 1
        assert CHUNK_ID in warnings[0].getMessage()
