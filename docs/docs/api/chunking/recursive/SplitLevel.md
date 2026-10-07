---
title: agrag.chunking.recursive.SplitLevel
sidebar_label: SplitLevel
---

# `agrag.chunking.recursive.SplitLevel` \{#agrag-chunking-recursive-SplitLevel}

Bases: <code>BaseModel</code>

One level of recursive split rules.

**Attributes:**

- [**delimiters**](#agrag-chunking-recursive-SplitLevel-delimiters) (<code>tuple\[str, ...\] | None</code>) – The strings to split on at this level. `None` means none.
- [**whitespace**](#agrag-chunking-recursive-SplitLevel-whitespace) (<code>bool</code>) – Whether to split on whitespace at this level.
- [**include_delim**](#agrag-chunking-recursive-SplitLevel-include_delim) (<code>Literal['prev', 'next'] | None</code>) – Whether a delimiter stays with the previous piece, the next
  piece, or is dropped.

## `delimiters` \{#agrag-chunking-recursive-SplitLevel-delimiters}

```python
delimiters: tuple[str, ...] | None = None
```

## `include_delim` \{#agrag-chunking-recursive-SplitLevel-include_delim}

```python
include_delim: Literal['prev', 'next'] | None = 'prev'
```

## `model_config` \{#agrag-chunking-recursive-SplitLevel-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `whitespace` \{#agrag-chunking-recursive-SplitLevel-whitespace}

```python
whitespace: bool = False
```
