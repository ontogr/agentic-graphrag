---
title: agrag.chunking.rules.DEFAULT_CHUNKING
sidebar_label: DEFAULT_CHUNKING
---

# `agrag.chunking.rules.DEFAULT_CHUNKING` \{#agrag-chunking-rules-DEFAULT_CHUNKING}

```python
DEFAULT_CHUNKING = Chunking(rules=(ChunkingRule(match=RuleMatch(loader_names=['docling']), chunker=DoclingChunker()),), fallback=RecursiveChunker(tokenizer='character', chunk_size=1024, min_characters_per_chunk=24))
```

The preset that `Graph` uses: `docling` loads go to `DoclingChunker`.

All other documents go to a `RecursiveChunker` with a 1024-character size.
