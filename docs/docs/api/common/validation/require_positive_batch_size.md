---
title: agrag.common.validation.require_positive_batch_size
sidebar_label: require_positive_batch_size
---

# `agrag.common.validation.require_positive_batch_size` \{#agrag-common-validation-require_positive_batch_size}

```python
require_positive_batch_size(batch_size:int) -> None
```

Make sure that a backend write's `batch_size` is usable.

Every backend chunks writes with `range(0, len(records), batch_size)`.
A non-positive value breaks that: zero raises `ValueError` from
`range` itself, and a negative value silently produces an empty range,
skipping every record without error.

**Parameters:**

- **batch_size** (<code>int</code>) – The batch size to check.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.
