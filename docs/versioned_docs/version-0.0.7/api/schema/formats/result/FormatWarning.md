---
title: agrag.schema.formats.result.FormatWarning
sidebar_label: FormatWarning
---

# `agrag.schema.formats.result.FormatWarning` \{#agrag-schema-formats-result-FormatWarning}

```python
FormatWarning(code:str, element:str, message:str) -> None
```

One thing an import dropped, changed or could not map.

**Attributes:**

- [**code**](#agrag-schema-formats-result-FormatWarning-code) (<code>str</code>) – A stable machine-readable name, such as `unknown_parent`.
- [**element**](#agrag-schema-formats-result-FormatWarning-element) (<code>str</code>) – The source element the warning is about.
- [**message**](#agrag-schema-formats-result-FormatWarning-message) (<code>str</code>) – A sentence that says what happened and how to fix it.

## `code` \{#agrag-schema-formats-result-FormatWarning-code}

```python
code: str
```

## `element` \{#agrag-schema-formats-result-FormatWarning-element}

```python
element: str
```

## `message` \{#agrag-schema-formats-result-FormatWarning-message}

```python
message: str
```
