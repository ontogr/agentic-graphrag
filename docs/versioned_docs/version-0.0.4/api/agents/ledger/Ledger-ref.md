---
title: agrag.agents.ledger.Ledger
sidebar_label: Ledger
---

# `agrag.agents.ledger.Ledger` \{#agrag-agents-ledger-Ledger}

```python
Ledger() -> None
```

Assigns and tracks stable citation keys for one agent run.

A key (E1, R1, C1 for entities, relations, and chunks) is
assigned the first time this run encounters that item, by
SearchResult.identity_key, and never reassigned within the run.
The agent is shown rendered evidence carrying these keys, never
raw SearchResults. A chunk result that has a parent shows the parent text under
the first child's key. Later children of that parent show their own text and
name the first key.

**Functions:**

- [**cite**](#agrag-agents-ledger-Ledger-cite) – Return this result's citation key, assigning one if new.
- [**render**](#agrag-agents-ledger-Ledger-render) – Return the markdown-with-key text the agent sees.
- [**resolve**](#agrag-agents-ledger-Ledger-resolve) – Return the SearchResult behind a citation key.

**Attributes:**

- [**keys**](#agrag-agents-ledger-Ledger-keys) (<code>list\[str\]</code>) – Return all citation keys assigned so far.

## `cite` \{#agrag-agents-ledger-Ledger-cite}

```python
cite(result:SearchResult) -> str
```

Return this result's citation key, assigning one if new.

**Parameters:**

- **result** (<code>[SearchResult](../../common/data_models/search_result/SearchResult.md)</code>) – The SearchResult to assign a key to.

**Returns:**

- <code>str</code> – The citation key (e.g. `E1`, `C3`).

## `keys` \{#agrag-agents-ledger-Ledger-keys}

```python
keys: list[str]
```

Return all citation keys assigned so far.

## `render` \{#agrag-agents-ledger-Ledger-render}

```python
render(result:SearchResult) -> str
```

Return the markdown-with-key text the agent sees.

**Parameters:**

- **result** (<code>[SearchResult](../../common/data_models/search_result/SearchResult.md)</code>) – The SearchResult to render.

**Returns:**

- <code>str</code> – Markdown text with the citation key and item summary.

## `resolve` \{#agrag-agents-ledger-Ledger-resolve}

```python
resolve(key:str) -> SearchResult | None
```

Return the SearchResult behind a citation key.

**Parameters:**

- **key** (<code>str</code>) – The citation key to look up.

**Returns:**

- <code>[SearchResult](../../common/data_models/search_result/SearchResult.md) | None</code> – The SearchResult, or None if the key is unknown.
