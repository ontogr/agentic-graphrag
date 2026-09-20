"""Tests for the Recipe data class and its preset instances.

Covers the fields of each preset (ENTITY, CHUNK, HYBRID, HYBRID_RERANKED,
GRAPH_EXPAND, TEXT2CYPHER) and that a custom Recipe can be constructed
directly with its own methods, bfs flag, and limit.
"""

from agrag.retrieval.recipes import (
    CHUNK,
    ENTITY,
    GRAPH_EXPAND,
    HYBRID,
    HYBRID_RERANKED,
    TEXT2CYPHER,
    Recipe,
)


class TestRecipe:
    """Recipe is a named, data-only configuration."""

    def test_entity_recipe(self) -> None:
        """ENTITY recipe searches only entities."""
        assert ENTITY.methods == ["entity"]
        assert ENTITY.bfs is False
        assert ENTITY.limit == 10

    def test_chunk_recipe(self) -> None:
        """CHUNK recipe searches only chunks."""
        assert CHUNK.methods == ["chunk"]

    def test_hybrid_recipe(self) -> None:
        """HYBRID recipe searches both entity and chunk."""
        assert "entity" in HYBRID.methods
        assert "chunk" in HYBRID.methods

    def test_hybrid_reranked_recipe(self) -> None:
        """HYBRID_RERANKED uses cross_encoder reranker."""
        assert HYBRID_RERANKED.reranker == "cross_encoder"

    def test_graph_expand_recipe(self) -> None:
        """GRAPH_EXPAND enables BFS."""
        assert GRAPH_EXPAND.bfs is True
        assert "entity" in GRAPH_EXPAND.methods

    def test_text2cypher_recipe(self) -> None:
        """TEXT2CYPHER recipe searches only the text2cypher retriever."""
        assert TEXT2CYPHER.methods == ["text2cypher"]
        assert TEXT2CYPHER.limit == 10
        assert TEXT2CYPHER.bfs is False

    def test_custom_recipe(self) -> None:
        """Custom recipes can be created."""
        r = Recipe(methods=["entity", "chunk"], bfs=True, limit=50)
        assert r.methods == ["entity", "chunk"]
        assert r.bfs is True
        assert r.limit == 50

    def test_min_score_defaults_to_none(self) -> None:
        """Every preset leaves the rerank score floor to settings."""
        for preset in (
            ENTITY,
            CHUNK,
            HYBRID,
            HYBRID_RERANKED,
            GRAPH_EXPAND,
            TEXT2CYPHER,
        ):
            assert preset.min_score is None

    def test_model_copy_overrides_min_score_without_mutating_preset(self) -> None:
        """A per-call override leaves the shared preset unmutated."""
        updated = HYBRID_RERANKED.model_copy(update={"min_score": 0.5})

        assert updated.min_score == 0.5
        assert HYBRID_RERANKED.min_score is None
