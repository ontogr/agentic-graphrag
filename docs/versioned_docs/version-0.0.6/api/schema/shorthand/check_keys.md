---
title: agrag.schema.shorthand.check_keys
sidebar_label: check_keys
---

# `agrag.schema.shorthand.check_keys` \{#agrag-schema-shorthand-check_keys}

```python
check_keys(body:Mapping[Any, object], allowed:Sequence[str], path:str, issues:Issues) -> None
```

Record an issue for every key outside `allowed`.
