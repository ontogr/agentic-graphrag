---
title: agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever
sidebar_label: Text2CypherRetriever
---

# `agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever` \{#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever}

```python
Text2CypherRetriever(*, graph_store:GraphStore, schema:GraphSchema, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](../base/Retriever.md)</code>

Let the agent ask structured questions via generated Cypher.

Calls a BAML function to generate a read-only Cypher query
against the graph's declared schema, runs reject_write_cypher as a
safety pre-filter, then bounds the query with a row limit and a
server-side transaction timeout before EXPLAIN and execution. A
query that fails to plan or to execute is regenerated once, carrying
a bounded, sanitized diagnostic of the failure. Rows that carry an
entity id are loaded from the graph before becoming a
SearchResult; relationship and chunk rows are parsed directly, under
the prompt's own aliases or any alias the model chose instead.
Scalar rows (for example counts or property values) become cited
`QueryValue` results so direct-query answers are not lost.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever-retrieve) – Generate and execute a Cypher query for the question.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – Where the generated query runs.
- **schema** (<code>[GraphSchema](../../../common/data_models/graph_schema/GraphSchema.md)</code>) – The graph's declared schema. Generation is grounded in
  this schema's labels and relation patterns, so a query the
  graph cannot answer is not generated.
- **settings** (<code>[RetrievalSettings](../../settings/RetrievalSettings.md) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the generation span and the BAML call spans.

## `name` \{#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever-name}

```python
name = 'text2cypher'
```

## `retrieve` \{#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int = 10) -> list[SearchResult]
```

Generate and execute a Cypher query for the question.

A query that fails to plan or to execute is regenerated once, with a
bounded, sanitized diagnostic of the first failure attached to the
generation call. A failure at any stage of the second attempt, a
query rejected by the write gate, or an unavailable database
raises. An empty list means the query ran and returned no rows.

**Parameters:**

- **query** (<code>str</code>) – The natural-language question.
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Ignored; text2cypher applies its own filters.
- **limit** (<code>int</code>) – Maximum results to return.

**Returns:**

- <code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code> – SearchResults from the generated query: entity results
  loaded from the graph; relation, chunk, and
  scalar rows parsed directly.

**Raises:**

- <code>UnsafeCypherError</code> – The generated query contains a write
  clause.
- <code>ValueError</code> – A stored entity node cannot be parsed.
- <code>Exception</code> – The LLM call failed, the BAML client is not
  installed, or the query failed to plan or run after the
  repair attempt.
