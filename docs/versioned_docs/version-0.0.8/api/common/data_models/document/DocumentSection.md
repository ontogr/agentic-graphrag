---
title: agrag.common.data_models.document.DocumentSection
sidebar_label: DocumentSection
---

# `agrag.common.data_models.document.DocumentSection` \{#agrag-common-data_models-document-DocumentSection}

Bases: <code>BaseModel</code>

One heading of a document and the content directly under it.

Sections are in reading order. A section has no text of its own: the units hold
it. Content before the first heading, or in a document with no headings, goes in
a section with an empty heading.

**Attributes:**

- [**heading**](#agrag-common-data_models-document-DocumentSection-heading) (<code>str</code>) – The heading text. Empty for a section made for content that has no
  heading.
- [**depth**](#agrag-common-data_models-document-DocumentSection-depth) (<code>int</code>) – The heading depth. A top-level heading has depth 1. A document title
  or a section made for content with no heading has depth 0.
- [**parent**](#agrag-common-data_models-document-DocumentSection-parent) (<code>int | None</code>) – The positional index in `Document.sections` of the section that
  contains this one. `None` for a section that sits directly under
  the document. The index must come before this section, and the
  parent must be shallower. Always an int index, never a key or id.
- [**source_id**](#agrag-common-data_models-document-DocumentSection-source_id) (<code>str | None</code>) – The id of the source record, such as a chat message id.
- [**units**](#agrag-common-data_models-document-DocumentSection-units) (<code>list\[[Unit](Unit.md)\]</code>) – The content directly under the heading, in reading order.

## `depth` \{#agrag-common-data_models-document-DocumentSection-depth}

```python
depth: int = Field(ge=0)
```

## `heading` \{#agrag-common-data_models-document-DocumentSection-heading}

```python
heading: str
```

## `parent` \{#agrag-common-data_models-document-DocumentSection-parent}

```python
parent: int | None = None
```

## `source_id` \{#agrag-common-data_models-document-DocumentSection-source_id}

```python
source_id: str | None = None
```

## `units` \{#agrag-common-data_models-document-DocumentSection-units}

```python
units: list[Unit] = Field(default_factory=list)
```
