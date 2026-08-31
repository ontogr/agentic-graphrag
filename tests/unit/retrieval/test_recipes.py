"""Tests for Recipe and preset recipes."""

from agrag.retrieval.recipes import (
    CHUNK,
    ENTITY,
    GRAPH_EXPAND,
    HYBRID,
    HYBRID_RERANKED,
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

    def test_custom_recipe(self) -> None:
        """Custom recipes can be created."""
        r = Recipe(methods=["entity", "chunk"], bfs=True, limit=50)
        assert r.methods == ["entity", "chunk"]
        assert r.bfs is True
        assert r.limit == 50
