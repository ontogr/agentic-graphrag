---
title: agrag.chunking.extras.byte_spans_to_char_spans
sidebar_label: byte_spans_to_char_spans
---

# `agrag.chunking.extras.byte_spans_to_char_spans` \{#agrag-chunking-extras-byte_spans_to_char_spans}

```python
byte_spans_to_char_spans(text:str, spans:list[tuple[int, int]]) -> list[tuple[int, int]]
```

Convert UTF-8 byte spans of `text` to character spans.

**Parameters:**

- **text** (<code>str</code>) – The text the byte offsets index once encoded as UTF-8.
- **spans** (<code>list\[tuple\[int, int\]\]</code>) – Half-open byte spans.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The same spans as character offsets. ASCII text returns the spans as given.
