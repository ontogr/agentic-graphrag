"""Tests for the traversal helpers in agrag.retrieval.methods.traversal.

Covers entity-id extraction for both entity and resolved-entity results (a
resolved entity seeds traversal with its members' raw ids, never its own id)
and the relation-type allowlist. Direction, relation-type narrowing, and scope
enforcement against a real graph run in the integration suite.
"""

from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.methods.traversal import (
    _intersect_relation_types,
    extract_entity_ids,
)


def _entity(name: str = "Acme", label: str = "Organization") -> Entity:
    """Build a minimal Entity."""
    return Entity(id=uuid4(), label=label, name=name)


def _result(entity: Any) -> SearchResult:
    """Wrap an entity in a SearchResult as a retriever would."""
    return SearchResult(item=entity, score=1.0, method="entity")


def _resolved(member_ids: list) -> ResolvedEntity:
    """Build a ResolvedEntity carrying the given member ids."""
    return ResolvedEntity(
        id=uuid4(), label="Organization", name="Acme", member_ids=member_ids
    )


class TestTraversal:
    """Tests scoped entity lookup and graph traversal helpers."""

    def test_extract_entity_ids_handles_resolved_entity_member_ids(self) -> None:
        """A resolved entity contributes its members' ids, never its own."""
        members = [uuid4(), uuid4()]
        resolved = _resolved(members)
        ids = extract_entity_ids([_result(resolved)])  # type: ignore[arg-type]
        assert ids == members
        assert resolved.id not in ids

    def test_extract_entity_ids_dedupes_and_skips_other_items(self) -> None:
        """Repeat ids are kept once and non-entity items are skipped."""
        entity = _entity()
        resolved = _resolved([entity.id, uuid4()])
        chunk = Chunk(
            id=uuid4(),
            document_id=uuid4(),
            text="text",
            provenance=TextProvenance(char_start=0, char_end=4),
        )
        ids = extract_entity_ids([_result(entity), _result(resolved), _result(chunk)])
        assert ids == [entity.id, resolved.member_ids[1]]

    @pytest.mark.parametrize(
        ("base", "requested", "expected"),
        [
            ([], "TREATS", ["TREATS"]),
            ([], None, []),
            (["WORKS_FOR", "TREATS"], "TREATS", ["TREATS"]),
            (["WORKS_FOR"], None, ["WORKS_FOR"]),
        ],
    )
    def test_intersect_relation_types_allowlist_semantics(
        self, base: list[str], requested: str | None, expected: list[str]
    ) -> None:
        """The four allowlist cases resolve as documented."""
        assert _intersect_relation_types(base, requested) == expected
