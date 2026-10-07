---
title: agrag.retrieval
sidebar_position: 11
---


# `agrag.retrieval` \{#agrag-retrieval}

Retrieval package: search engine, fusion, reranking, and retrievers.

**Modules:**

- [**community_context**](community_context/index.md) – Community-report enrichment: local-search-style budget-capped context.
- [**errors**](errors/index.md) – Errors that the retrieval layer raises.
- [**filters**](filters/index.md) – Constraints applied across every retrieval method in one call.
- [**fusion**](fusion/index.md) – Reciprocal Rank Fusion: combine ranked results from multiple methods.
- [**methods**](methods/index.md) – Low-level search method helpers shared by retrievers.
- [**recipes**](recipes/index.md) – Named, data-only configurations of what SearchEngine runs.
- [**rerank**](rerank/index.md) – Rerankers that reorder fused search results.
- [**resolved_entities**](resolved_entities/index.md) – Loading helpers for resolved entities.
- [**retrievers**](retrievers/index.md) – Retriever implementations for entity, chunk, BFS, and text2cypher search.
- [**search_engine**](search_engine/index.md) – Retrieval's public entry point, independent of Graph.
- [**settings**](settings/index.md) – Env-backed configuration for retrieval methods and fusion.
- [**tracing**](tracing/index.md) – Span helpers shared by the retrieval spans.

**Classes:**

- [**AllRetrievalMethodsFailedError**](errors/AllRetrievalMethodsFailedError.md) – Every retrieval method a Recipe named failed.
- [**BFSRetriever**](retrievers/bfs/BFSRetriever.md) – Graph traversal from seed entity ids.
- [**ChunkRetriever**](retrievers/chunk/ChunkRetriever.md) – Dense chunk search via vector similarity.
- [**CommunityRetriever**](retrievers/community/CommunityRetriever.md) – Dense search over community reports, for direct thematic questions.
- [**EntityRetriever**](retrievers/entity/EntityRetriever.md) – Dense entity search via vector similarity.
- [**Recipe**](recipes/Recipe.md) – A named configuration of what SearchEngine runs for a query.
- [**RetrievalError**](errors/RetrievalError.md) – The base class for every retrieval error.
- [**RetrievalSettings**](settings/RetrievalSettings.md) – Configuration for retrieval methods and fusion.
- [**Retriever**](retrievers/base/Retriever.md) – One retrieval method: given a query, return SearchResults.
- [**ScopeDeniedError**](errors/ScopeDeniedError.md) – A request asked for data outside the caller's permitted scope.
- [**SearchEngine**](search_engine/SearchEngine.md) – Retrieval's public entry point, independent of Graph.
- [**SearchFilters**](filters/SearchFilters.md) – Constraints applied across every retrieval method in one call.
- [**Text2CypherRetriever**](retrievers/text2cypher/Text2CypherRetriever.md) – Let the agent ask structured questions via generated Cypher.
- [**UnknownRecipeMethodError**](errors/UnknownRecipeMethodError.md) – A Recipe named a method SearchEngine does not know how to run.

**Attributes:**

- [**CHUNK**](recipes/CHUNK.md) –
- [**ENTITY**](recipes/ENTITY.md) –
- [**GRAPH_EXPAND**](recipes/GRAPH_EXPAND.md) –
- [**HYBRID**](recipes/HYBRID.md) –
- [**HYBRID_RERANKED**](recipes/HYBRID_RERANKED.md) –
- [**TEXT2CYPHER**](recipes/TEXT2CYPHER.md) –
- [**THEMATIC**](recipes/THEMATIC.md) –
