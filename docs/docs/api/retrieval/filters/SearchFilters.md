---
title: agrag.retrieval.filters.SearchFilters
sidebar_label: SearchFilters
---

# `agrag.retrieval.filters.SearchFilters` \{#agrag-retrieval-filters-SearchFilters}

Bases: <code>BaseModel</code>

Constraints applied across every retrieval method in one call.

**Attributes:**

- [**labels**](#agrag-retrieval-filters-SearchFilters-labels) (<code>list\[str\]</code>) – Entity labels a result must have, when searching
  entities.
- [**relation_types**](#agrag-retrieval-filters-SearchFilters-relation_types) (<code>list\[str\]</code>) – Relation types a traversal can cross.
- [**document_ids**](#agrag-retrieval-filters-SearchFilters-document_ids) (<code>list\[str\]</code>) – Restrict results to entities and chunks from these
  source documents.
- [**properties**](#agrag-retrieval-filters-SearchFilters-properties) (<code>dict\[str, Any\]</code>) – Exact-match property filters, applied
  identically to vector-store payload filters and Cypher
  WHERE clauses.

**Functions:**

- [**to_cypher_where**](#agrag-retrieval-filters-SearchFilters-to_cypher_where) – Return a parameterized WHERE clause fragment.
- [**to_payload_filter**](#agrag-retrieval-filters-SearchFilters-to_payload_filter) – Return a flat-dict filter for VectorStore search calls.
- [**to_property_filter**](#agrag-retrieval-filters-SearchFilters-to_property_filter) – Return a flat-dict filter over node properties only.

## `document_ids` \{#agrag-retrieval-filters-SearchFilters-document_ids}

```python
document_ids: list[str] = Field(default_factory=list)
```

## `labels` \{#agrag-retrieval-filters-SearchFilters-labels}

```python
labels: list[str] = Field(default_factory=list)
```

## `properties` \{#agrag-retrieval-filters-SearchFilters-properties}

```python
properties: dict[str, Any] = Field(default_factory=dict)
```

## `relation_types` \{#agrag-retrieval-filters-SearchFilters-relation_types}

```python
relation_types: list[str] = Field(default_factory=list)
```

## `to_cypher_where` \{#agrag-retrieval-filters-SearchFilters-to_cypher_where}

```python
to_cypher_where(node_var:str = 'node') -> tuple[str, dict[str, Any]]
```

Return a parameterized WHERE clause fragment.

Labels are emitted as native Cypher node labels (`node:Label`)
rather than property filters, since Neo4j represents entity types
as labels on nodes. Document-id and property filters go through
`filter_clause` as before.

**Parameters:**

- **node_var** (<code>str</code>) – The Cypher variable bound to the node.

**Returns:**

- <code>tuple\[str, dict\[str, Any\]\]</code> – The WHERE clause text and parameters dict.

## `to_payload_filter` \{#agrag-retrieval-filters-SearchFilters-to_payload_filter}

```python
to_payload_filter() -> dict[str, Any]
```

Return a flat-dict filter for VectorStore search calls.

Labels become a `label` payload key, which is how a
VectorStore records the graph label a record came from. A
GraphStore holds labels on the node itself, not as a property,
so the native path uses `to_property_filter` instead and
selects labels by the index it searches.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict suitable for VectorStore.search/hybrid_search
- <code>dict\[str, Any\]</code> – filters parameter.

## `to_property_filter` \{#agrag-retrieval-filters-SearchFilters-to_property_filter}

```python
to_property_filter() -> dict[str, Any]
```

Return a flat-dict filter over node properties only.

Excludes `labels`, which are node labels rather than
properties on every graph backend this project supports.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict of property name to expected value, where a list
- <code>dict\[str, Any\]</code> – value means any of.
