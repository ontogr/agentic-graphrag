---
title: agrag.chunking.rules.ChunkingRule
sidebar_label: ChunkingRule
---

# `agrag.chunking.rules.ChunkingRule` \{#agrag-chunking-rules-ChunkingRule}

Bases: <code>BaseModel</code>

A match and the chunker for the documents it matches.

**Attributes:**

- [**match**](#agrag-chunking-rules-ChunkingRule-match) (<code>[RuleMatch](RuleMatch.md)</code>) – The documents this rule applies to.
- [**chunker**](#agrag-chunking-rules-ChunkingRule-chunker) (<code>SerializeAsAny\[[Chunker](../base/Chunker.md)\]</code>) – The chunker those documents get.

## `chunker` \{#agrag-chunking-rules-ChunkingRule-chunker}

```python
chunker: SerializeAsAny[Chunker]
```

## `match` \{#agrag-chunking-rules-ChunkingRule-match}

```python
match: RuleMatch
```

## `model_config` \{#agrag-chunking-rules-ChunkingRule-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```
