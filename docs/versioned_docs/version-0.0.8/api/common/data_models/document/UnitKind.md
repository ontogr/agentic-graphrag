---
title: agrag.common.data_models.document.UnitKind
sidebar_label: UnitKind
---

# `agrag.common.data_models.document.UnitKind` \{#agrag-common-data_models-document-UnitKind}

Bases: <code>StrEnum</code>

The kind of content in a unit.

**Attributes:**

- [**PARAGRAPH**](#agrag-common-data_models-document-UnitKind-PARAGRAPH) – A paragraph of running text.
- [**LIST**](#agrag-common-data_models-document-UnitKind-LIST) – A list. One unit holds all the items of one list.
- [**CODE**](#agrag-common-data_models-document-UnitKind-CODE) – A block of code.
- [**FORMULA**](#agrag-common-data_models-document-UnitKind-FORMULA) – A formula.
- [**FOOTNOTE**](#agrag-common-data_models-document-UnitKind-FOOTNOTE) – A footnote.
- [**TABLE**](#agrag-common-data_models-document-UnitKind-TABLE) – A table. Its rows are in `Unit.rows`.
- [**FIGURE**](#agrag-common-data_models-document-UnitKind-FIGURE) – A picture, chart, or diagram. Its text is the caption.

## `CODE` \{#agrag-common-data_models-document-UnitKind-CODE}

```python
CODE = 'code'
```

## `FIGURE` \{#agrag-common-data_models-document-UnitKind-FIGURE}

```python
FIGURE = 'figure'
```

## `FOOTNOTE` \{#agrag-common-data_models-document-UnitKind-FOOTNOTE}

```python
FOOTNOTE = 'footnote'
```

## `FORMULA` \{#agrag-common-data_models-document-UnitKind-FORMULA}

```python
FORMULA = 'formula'
```

## `LIST` \{#agrag-common-data_models-document-UnitKind-LIST}

```python
LIST = 'list'
```

## `PARAGRAPH` \{#agrag-common-data_models-document-UnitKind-PARAGRAPH}

```python
PARAGRAPH = 'paragraph'
```

## `TABLE` \{#agrag-common-data_models-document-UnitKind-TABLE}

```python
TABLE = 'table'
```
