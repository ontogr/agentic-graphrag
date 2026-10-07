---
title: agrag.chunking.parent_child.ParentChildChunker
sidebar_label: ParentChildChunker
---

# `agrag.chunking.parent_child.ParentChildChunker` \{#agrag-chunking-parent_child-ParentChildChunker}

Bases: <code>[Chunker](../base/Chunker.md)</code>

Cuts a document into parent chunks and cuts each parent into child chunks.

Extraction runs on the parents, which have `level=1`. The children have
`level=0` and a `parent_id`, and only the children are embedded and searched.
A search hit returns the child with its parent attached.

A child never crosses a parent boundary, because the child strategy cuts each
parent alone. Text of a parent that the child strategy leaves out gets a child of
its own, so all non-blank text can be found by search. A parent that the child
strategy leaves without any piece gets one child with the span of the parent.

The chunker returns all parents, then all children. Indexes count from 0 at each
level.

**Attributes:**

- [**parent**](#agrag-chunking-parent_child-ParentChildChunker-parent) (<code>SerializeAsAny\[[SpanChunker](../base/SpanChunker.md)\]</code>) – The strategy that cuts the document into parents.
- [**child**](#agrag-chunking-parent_child-ParentChildChunker-child) (<code>SerializeAsAny\[[SpanChunker](../base/SpanChunker.md)\]</code>) – The strategy that cuts each parent into children.

**Functions:**

- [**chunk**](#agrag-chunking-parent_child-ParentChildChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-parent_child-ParentChildChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-parent_child-ParentChildChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-parent_child-ParentChildChunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-parent_child-ParentChildChunker-settings) – Return the strategy name and every setting as JSON-safe data.

## `child` \{#agrag-chunking-parent_child-ParentChildChunker-child}

```python
child: SerializeAsAny[SpanChunker] = Field(default_factory=_default_child)
```

## `chunk` \{#agrag-chunking-parent_child-ParentChildChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](../../common/data_models/document/Document-ref.md)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](../../common/data_models/chunk/Chunk-ref.md)\]</code> – The chunks, in document order, each with `chunker` and
  `chunker_hash` set. A strategy that sets `chunker` itself keeps
  its value.

**Raises:**

- <code>[ChunkingError](../base/ChunkingError.md)</code> – The strategy returned chunks that break the contract.

## `fingerprint` \{#agrag-chunking-parent_child-ParentChildChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `model_config` \{#agrag-chunking-parent_child-ParentChildChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-parent_child-ParentChildChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

## `model_post_init` \{#agrag-chunking-parent_child-ParentChildChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

## `parent` \{#agrag-chunking-parent_child-ParentChildChunker-parent}

```python
parent: SerializeAsAny[SpanChunker] = Field(default_factory=_default_parent)
```

## `settings` \{#agrag-chunking-parent_child-ParentChildChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `strategy` \{#agrag-chunking-parent_child-ParentChildChunker-strategy}

```python
strategy: str
```

The strategy name, `"parent-child"`.
