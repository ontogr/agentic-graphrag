---
title: agrag.chunking.ChunkingRule
sidebar_label: ChunkingRule
---

# `agrag.chunking.ChunkingRule` \{#agrag-chunking-ChunkingRule}

Bases: <code>BaseModel</code>

A match and the chunker for the documents it matches.

**Attributes:**

- [**match**](#agrag-chunking-ChunkingRule-match) (<code>[RuleMatch](rules/RuleMatch.md)</code>) – The documents this rule applies to.
- [**chunker**](#agrag-chunking-ChunkingRule-chunker) (<code>SerializeAsAny\[[Chunker](base/Chunker.md)\]</code>) – The chunker those documents get.

## `chunker` \{#agrag-chunking-ChunkingRule-chunker}

```python
chunker: SerializeAsAny[Chunker]
```

## `match` \{#agrag-chunking-ChunkingRule-match}

```python
match: RuleMatch
```

## `model_config` \{#agrag-chunking-ChunkingRule-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```
