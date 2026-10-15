---
title: agrag.common.data_models.navigation.NavigationRelation
sidebar_label: NavigationRelation
---

# `agrag.common.data_models.navigation.NavigationRelation` \{#agrag-common-data_models-navigation-NavigationRelation}

Bases: <code>StrEnum</code>

The neighbor relation a navigation call follows.

**Attributes:**

- [**PARENT**](#agrag-common-data_models-navigation-NavigationRelation-PARENT) – The section or sections that hold the passage.
- [**CHILDREN**](#agrag-common-data_models-navigation-NavigationRelation-CHILDREN) – The other passages under the same parent node.
- [**SIBLINGS**](#agrag-common-data_models-navigation-NavigationRelation-SIBLINGS) – The other sections under the same parent section.
- [**PREVIOUS**](#agrag-common-data_models-navigation-NavigationRelation-PREVIOUS) – The passage before this one in reading order.
- [**NEXT**](#agrag-common-data_models-navigation-NavigationRelation-NEXT) – The passage after this one in reading order.
- [**TABLE_CONTEXT**](#agrag-common-data_models-navigation-NavigationRelation-TABLE_CONTEXT) – The row passages before and after a table passage, with
  the table itself.

## `CHILDREN` \{#agrag-common-data_models-navigation-NavigationRelation-CHILDREN}

```python
CHILDREN = 'children'
```

## `NEXT` \{#agrag-common-data_models-navigation-NavigationRelation-NEXT}

```python
NEXT = 'next'
```

## `PARENT` \{#agrag-common-data_models-navigation-NavigationRelation-PARENT}

```python
PARENT = 'parent'
```

## `PREVIOUS` \{#agrag-common-data_models-navigation-NavigationRelation-PREVIOUS}

```python
PREVIOUS = 'previous'
```

## `SIBLINGS` \{#agrag-common-data_models-navigation-NavigationRelation-SIBLINGS}

```python
SIBLINGS = 'siblings'
```

## `TABLE_CONTEXT` \{#agrag-common-data_models-navigation-NavigationRelation-TABLE_CONTEXT}

```python
TABLE_CONTEXT = 'table_context'
```
