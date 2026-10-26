---
title: agrag.ingestion.merge.PropertyRules
sidebar_label: PropertyRules
---

# `agrag.ingestion.merge.PropertyRules` \{#agrag-ingestion-merge-PropertyRules}

```python
PropertyRules(rules:dict[str, PropertyRule] = dict(), default:PropertyStrategy = PropertyStrategy.KEEP_FIRST) -> None
```

Per-property conflict resolution, with a default for unlisted properties.

**Attributes:**

- [**rules**](#agrag-ingestion-merge-PropertyRules-rules) (<code>dict\[str, [PropertyRule](PropertyRule.md)\]</code>) – Property name to resolver, for properties needing a specific rule.
- [**default**](#agrag-ingestion-merge-PropertyRules-default) (<code>[PropertyStrategy](PropertyStrategy.md)</code>) – Strategy applied to a property with no entry in rules.

## `default` \{#agrag-ingestion-merge-PropertyRules-default}

```python
default: PropertyStrategy = PropertyStrategy.KEEP_FIRST
```

## `rules` \{#agrag-ingestion-merge-PropertyRules-rules}

```python
rules: dict[str, PropertyRule] = field(default_factory=dict)
```
