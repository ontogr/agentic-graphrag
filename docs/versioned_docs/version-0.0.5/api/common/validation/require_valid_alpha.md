---
title: agrag.common.validation.require_valid_alpha
sidebar_label: require_valid_alpha
---

# `agrag.common.validation.require_valid_alpha` \{#agrag-common-validation-require_valid_alpha}

```python
require_valid_alpha(alpha:float) -> None
```

Make sure that a `hybrid_search` `alpha` is a valid dense and keyword weight.

`alpha` is only meaningful in `[0.0, 1.0]`. `1.0` is pure dense
and `0.0` is pure keyword. Outside that range, backends behave
differently. Qdrant client-side blend still produces a
mathematically well-defined but meaningless score, while a backend
native ranker can reject the value outright.

**Parameters:**

- **alpha** (<code>float</code>) – The dense/keyword balance to check.

**Raises:**

- <code>ValueError</code> – `alpha` is outside `[0.0, 1.0]`.
