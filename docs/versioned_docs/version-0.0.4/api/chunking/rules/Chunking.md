---
title: agrag.chunking.rules.Chunking
sidebar_label: Chunking
---

# `agrag.chunking.rules.Chunking` \{#agrag-chunking-rules-Chunking}

Bases: <code>BaseModel</code>

An ordered list of chunking rules and a fallback chunker.

The first rule that matches a document picks its chunker. A document that no
rule matches gets `fallback`.

**Attributes:**

- [**rules**](#agrag-chunking-rules-Chunking-rules) (<code>tuple\[[ChunkingRule](ChunkingRule.md), ...\]</code>) – The rules, most specific first.
- [**fallback**](#agrag-chunking-rules-Chunking-fallback) (<code>SerializeAsAny\[[Chunker](../base/Chunker.md)\]</code>) – The chunker for documents that no rule matches.

**Functions:**

- [**fingerprint**](#agrag-chunking-rules-Chunking-fingerprint) – Return a hash of every rule match and every chunker setting.
- [**select**](#agrag-chunking-rules-Chunking-select) – Pick the chunker for a document.

## `fallback` \{#agrag-chunking-rules-Chunking-fallback}

```python
fallback: SerializeAsAny[Chunker]
```

## `fingerprint` \{#agrag-chunking-rules-Chunking-fingerprint}

```python
fingerprint() -> str
```

Return a hash of every rule match and every chunker setting.

## `model_config` \{#agrag-chunking-rules-Chunking-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `rules` \{#agrag-chunking-rules-Chunking-rules}

```python
rules: tuple[ChunkingRule, ...] = ()
```

## `select` \{#agrag-chunking-rules-Chunking-select}

```python
select(document:Document) -> tuple[int | None, Chunker]
```

Pick the chunker for a document.

**Parameters:**

- **document** (<code>[Document](../../common/data_models/document/Document-ref.md)</code>) – The document to chunk.

**Returns:**

- <code>int | None</code> – The index of the first matching rule and its chunker, or `None` and
- <code>[Chunker](../base/Chunker.md)</code> – the fallback when no rule matches.
