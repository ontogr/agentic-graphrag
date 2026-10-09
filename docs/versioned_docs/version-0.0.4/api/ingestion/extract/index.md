---
title: agrag.ingestion.extract
sidebar_label: extract
---

# `agrag.ingestion.extract` \{#agrag-ingestion-extract}

The Extractor interface: reads one Chunk and produces an ExtractionResult.

**Classes:**

- [**BAMLExtractor**](BAMLExtractor.md) – Extracts with an LLM, via a BAML function and a runtime ClientRegistry.
- [**EscalatingExtractor**](EscalatingExtractor.md) – Runs a cheap primary extractor first, escalating per chunk when it's weak.
- [**ExtractionLLMSettings**](ExtractionLLMSettings.md) – Env-backed LLM client config for the extraction role.
- [**Extractor**](Extractor.md) – Reads one Chunk and produces the entities and relations it contains.
- [**ExtractorMissingExtraError**](ExtractorMissingExtraError.md) – An Extractor needs a package extra that is not installed.
- [**GlinerExtractor**](GlinerExtractor.md) – Extracts locally with a GLiNER2.5 model. No network call.
