---
title: agrag.common.data_models.navigation.NavigationItem
sidebar_label: NavigationItem
---

# `agrag.common.data_models.navigation.NavigationItem` \{#agrag-common-data_models-navigation-NavigationItem}

Bases: <code>BaseModel</code>

One passage returned by a navigation call.

**Attributes:**

- [**evidence_id**](#agrag-common-data_models-navigation-NavigationItem-evidence_id) (<code>str</code>) – The evidence id of the passage. Pass it to fetch,
  check_citations or navigate.
- [**document_key**](#agrag-common-data_models-navigation-NavigationItem-document_key) (<code>str</code>) – The key of the document the passage belongs to.
- [**heading_path**](#agrag-common-data_models-navigation-NavigationItem-heading_path) (<code>list\[str\]</code>) – The headings above the passage, from the outermost down.
- [**kind**](#agrag-common-data_models-navigation-NavigationItem-kind) (<code>Literal['text', 'table']</code>) – `"text"` for running text and `"table"` for a table passage.
- [**text**](#agrag-common-data_models-navigation-NavigationItem-text) (<code>str</code>) – The passage text, cut to the character budget of the call.
- [**text_truncated**](#agrag-common-data_models-navigation-NavigationItem-text_truncated) (<code>bool</code>) – True when the text was cut to fit the character budget.
- [**location**](#agrag-common-data_models-navigation-NavigationItem-location) (<code>[EvidenceLocation](../evidence/EvidenceLocation.md)</code>) – The offsets or pages of the passage.

## `document_key` \{#agrag-common-data_models-navigation-NavigationItem-document_key}

```python
document_key: str
```

## `evidence_id` \{#agrag-common-data_models-navigation-NavigationItem-evidence_id}

```python
evidence_id: str
```

## `heading_path` \{#agrag-common-data_models-navigation-NavigationItem-heading_path}

```python
heading_path: list[str] = Field(default_factory=list)
```

## `kind` \{#agrag-common-data_models-navigation-NavigationItem-kind}

```python
kind: Literal['text', 'table']
```

## `location` \{#agrag-common-data_models-navigation-NavigationItem-location}

```python
location: EvidenceLocation
```

## `text` \{#agrag-common-data_models-navigation-NavigationItem-text}

```python
text: str
```

## `text_truncated` \{#agrag-common-data_models-navigation-NavigationItem-text_truncated}

```python
text_truncated: bool = False
```
