"""Constraints applied across every retrieval method in one call."""

from typing import Any

from pydantic import BaseModel, Field

from agrag.cypher.entities import filter_clause, validate_identifier


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

        Labels are emitted as native Cypher node labels (``node:Label``)
        rather than property filters, since Neo4j represents entity types
        as labels on nodes.  Document-id and property filters go through
        ``filter_clause`` as before.

        Args:
            node_var: The Cypher variable bound to the node.

        Returns:
            The WHERE clause text and parameters dict.
        """
        # Labels become native node-label checks.
        label_clauses: list[str] = []
        for lbl in self.labels:
            validate_identifier(lbl)
            label_clauses.append(f"{node_var}:{lbl}")

        # Remaining filters go through filter_clause.
        combined: dict[str, Any] = {}
        if self.document_ids:
            combined["document_id"] = self.document_ids
        for key, value in self.properties.items():
            combined[key] = value
        where, params = filter_clause(combined, node_var=node_var)

        # Merge label clauses into the WHERE fragment.
        all_clauses: list[str] = []
        if label_clauses:
            all_clauses.extend(label_clauses)
        if where:
            all_clauses.append(where[6:])  # strip "WHERE " prefix
        if not all_clauses:
            return "", {}
        return "WHERE " + " AND ".join(all_clauses), params
