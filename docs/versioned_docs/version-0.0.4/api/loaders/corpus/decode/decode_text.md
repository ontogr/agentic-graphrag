---
title: agrag.loaders.corpus.decode.decode_text
sidebar_label: decode_text
---

# `agrag.loaders.corpus.decode.decode_text` \{#agrag-loaders-corpus-decode-decode_text}

```python
decode_text(raw:bytes, opts:ReadOptions) -> DecodedText
```

Decode raw source bytes into normalized text.

This function detects the encoding, applies `opts.normalization` and hashes the
result. It raises `DecodeError` instead of returning garbled text.

**Parameters:**

- **raw** (<code>bytes</code>) – The raw source bytes.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options. `opts.encoding` forces a specific codec when set.

**Returns:**

- <code>[DecodedText](../types/DecodedText.md)</code> – The decoded text with its encoding and hash.

**Raises:**

- <code>[DecodeError](../errors/DecodeError.md)</code> – The bytes do not decode under the forced encoding, or detection
