"""Constraints applied across every retrieval method in one call."""

from typing import Any

from pydantic import BaseModel, Field

from agrag.cypher.entities import filter_clause


class SearchFilters(BaseModel):
    """Constraints applied across every retrieval method in one call.

    Attributes:
        labels: Entity labels a result must have, when searching
            entities.
        relation_types: Relation types a traversal may cross.
        document_ids: Restrict chunk results to these source
            documents.
        properties: Exact-match property filters, applied
            identically to vector-store payload filters and Cypher
            WHERE clauses.
    """

    labels: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)

    def to_payload_filter(self) -> dict[str, Any]:
        """Return a flat-dict filter for VectorStore search calls.

        Returns:
            A dict suitable for VectorStore.search/hybrid_search
            filters parameter.
        """
        result: dict[str, Any] = {}
        if self.labels:
            result["label"] = self.labels
        if self.document_ids:
            result["document_id"] = self.document_ids
        for key, value in self.properties.items():
            result[key] = value
        return result

    def to_cypher_where(self, node_var: str = "node") -> tuple[str, dict[str, Any]]:
        """Return a parameterized WHERE clause fragment.

        Combines label, document_id, and property filters into a
        single WHERE clause using agrag.cypher's filter_clause.

        Args:
            node_var: The Cypher variable bound to the node.

        Returns:
            The WHERE clause text and parameters dict.
        """
        combined: dict[str, Any] = {}
        if self.labels:
            combined["label"] = self.labels
        if self.document_ids:
            combined["document_id"] = self.document_ids
        for key, value in self.properties.items():
            combined[key] = value
        return filter_clause(combined, node_var=node_var)
