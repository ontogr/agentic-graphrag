---
title: agrag.chunking.extras
sidebar_label: extras
---

# `agrag.chunking.extras` \{#agrag-chunking-extras}

Opt-in chunkers that need a package extra: semantic, neural and code.

**Classes:**

- [**CodeChunker**](CodeChunker.md) – Cuts source code along its syntax tree.
- [**NeuralChunker**](NeuralChunker.md) – Cuts where a token classification model predicts a topic break.
- [**SemanticChunker**](SemanticChunker.md) – Cuts where the meaning of neighbouring sentences changes.

**Functions:**

- [**byte_spans_to_char_spans**](byte_spans_to_char_spans.md) – Convert UTF-8 byte spans of `text` to character spans.
