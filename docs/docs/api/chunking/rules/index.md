---
title: agrag.chunking.rules
sidebar_label: rules
---

# `agrag.chunking.rules` \{#agrag-chunking-rules}

Chunking rules: which chunker a document gets, as data.

**Classes:**

- [**Chunking**](Chunking.md) – An ordered list of chunking rules and a fallback chunker.
- [**ChunkingRule**](ChunkingRule.md) – A match and the chunker for the documents it matches.
- [**RuleMatch**](RuleMatch.md) – The documents a rule applies to.

**Attributes:**

- [**DEFAULT_CHUNKING**](DEFAULT_CHUNKING.md) – The preset that `Graph` uses: `docling` loads go to `DoclingChunker`.
