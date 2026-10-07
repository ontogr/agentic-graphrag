---
title: agrag.ingestion.extract
sidebar_label: extract
---

# `agrag.ingestion.extract` \{#agrag-ingestion-extract}

The Extractor interface: reads one Chunk and produces an ExtractionResult.

**Classes:**

- [**BAMLExtractor**](BAMLExtractor.md) – Extract entities and relations with an LLM through a typed BAML function.
- [**EscalatingExtractor**](EscalatingExtractor.md) – Run a cheap extractor on every chunk and a stronger one on weak results.
- [**ExtractionLLMSettings**](ExtractionLLMSettings.md) – Env-backed LLM client configuration for the extraction role.
- [**Extractor**](Extractor.md) – Reads one chunk and returns the entities and relations it contains.
- [**ExtractorMissingExtraError**](ExtractorMissingExtraError.md) – An Extractor needs a package extra that is not installed.
- [**GlinerExtractor**](GlinerExtractor.md) – Extracts entities and relations with a local GLiNER2.5 model.
