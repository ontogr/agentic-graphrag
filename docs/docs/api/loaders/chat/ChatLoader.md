---
title: agrag.loaders.chat.ChatLoader
sidebar_label: ChatLoader
---

# `agrag.loaders.chat.ChatLoader` \{#agrag-loaders-chat-ChatLoader}

Bases: <code>[ProseLoader](../base/ProseLoader.md)</code>

Reads a file of chat messages as one document with a section for each message.

Each message is a JSON object with a `role` and a `content` string, and an
optional `id`. A `.jsonl` or `.ndjson` file has one message per line. A
`.json` file holds an array of messages. The document text is one
`[role] content` block per message, separated by a blank line. Each message is
a section at depth 1 with the role as its heading and the message id as its
`source_id`.

The loader is not registered for any extension, because `.jsonl` belongs to the
record loader. Pass `loader=ChatLoader()` with a single-file source.

**Attributes:**

- [**extensions**](#agrag-loaders-chat-ChatLoader-extensions) – The `.jsonl`, `.ndjson` and `.json` extensions.

**Functions:**

- [**is_available**](#agrag-loaders-chat-ChatLoader-is_available) – Return whether this loader can run in this process.
- [**load**](#agrag-loaders-chat-ChatLoader-load) – Yield one prose Document that holds every message.

## `extensions` \{#agrag-loaders-chat-ChatLoader-extensions}

```python
extensions = frozenset({'.jsonl', '.ndjson', '.json'})
```

## `extra` \{#agrag-loaders-chat-ChatLoader-extra}

```python
extra: str | None = None
```

## `family` \{#agrag-loaders-chat-ChatLoader-family}

```python
family = DocumentFamily.PROSE
```

## `is_available` \{#agrag-loaders-chat-ChatLoader-is_available}

```python
is_available() -> bool
```

Return whether this loader can run in this process.

A loader with no extra is always available. A loader with an extra is
available when its package can be found. The check does not import the
package, so an installed package that fails to import still counts.

## `load` \{#agrag-loaders-chat-ChatLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one prose Document that holds every message.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options.
- **start_at** (<code>int</code>) – Ignored by prose loaders.

**Yields:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – One Document, or none when the source has no messages.

**Raises:**

- <code>[MalformedRecordError](../errors/MalformedRecordError.md)</code> – A message is not a JSON object with a non-empty
  string `role` and a string `content`, an `id` repeats an
  earlier one, or the source is not valid JSON of the expected shape.

## `mime_types` \{#agrag-loaders-chat-ChatLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
