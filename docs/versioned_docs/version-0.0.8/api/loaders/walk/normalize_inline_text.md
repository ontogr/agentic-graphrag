---
title: agrag.loaders.walk.normalize_inline_text
sidebar_label: normalize_inline_text
---

# `agrag.loaders.walk.normalize_inline_text` \{#agrag-loaders-walk-normalize_inline_text}

```python
normalize_inline_text(text:str, opts:ReadOptions) -> tuple[str, Normalization]
```

Normalize text that a caller passed in memory.

Inline text has no bytes to decode, so only the Unicode form applies.

**Parameters:**

- **text** (<code>str</code>) – The text as the caller gave it.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options. Only `opts.normalization.unicode_form` is used.

**Returns:**

- <code>tuple\[str, [Normalization](../../common/data_models/normalization/Normalization-ref.md)\]</code> – The normalized text and the normalization to record on its document.
