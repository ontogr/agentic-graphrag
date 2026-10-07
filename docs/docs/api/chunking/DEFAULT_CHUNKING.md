---
title: agrag.chunking.DEFAULT_CHUNKING
sidebar_label: DEFAULT_CHUNKING
---

# `agrag.chunking.DEFAULT_CHUNKING` \{#agrag-chunking-DEFAULT_CHUNKING}

```python
DEFAULT_CHUNKING = Chunking(rules=(ChunkingRule(match=RuleMatch(loader_names=['docling']), chunker=DoclingChunker()),), fallback=RecursiveChunker(tokenizer='character', chunk_size=1024, min_characters_per_chunk=24))
```
