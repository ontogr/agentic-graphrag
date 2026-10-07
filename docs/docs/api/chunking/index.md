---
title: agrag.chunking
sidebar_position: 3
---


# `agrag.chunking` \{#agrag-chunking}

Chunking: how a Document becomes Chunks.

A `Chunker` splits one document. A `Chunking` holds the rules that pick a chunker
for each document, and `DEFAULT_CHUNKING` is the preset that `Graph` uses.

**Modules:**

- [**base**](base/index.md) – The Chunker contract: how a Document becomes Chunks, and how that is recorded.
- [**docling**](docling/index.md) – Docling-native chunking.
- [**extras**](extras/index.md) – Opt-in chunkers that need a package extra: semantic, neural and code.
- [**heading**](heading/index.md) – The heading-aware strategy: sections packed to a token budget.
- [**parent_child**](parent_child/index.md) – The parent-child strategy: large parents to extract, small children to search.
- [**recursive**](recursive/index.md) – The recursive strategy: split on the coarsest delimiter that fits the budget.
- [**rules**](rules/index.md) – Chunking rules: which chunker a document gets, as data.
- [**sentence**](sentence/index.md) – The sentence strategy: whole sentences packed up to a token budget.
- [**token**](token/index.md) – The token strategy: fixed-size windows of tokens, with optional overlap.
- [**turns**](turns/index.md) – The turn-window strategy: whole chat turns packed to a token budget.

**Classes:**

- [**Chunker**](base/Chunker.md) – Splits one Document into Chunks and builds their provenance.
- [**ChunkerMissingExtraError**](base/ChunkerMissingExtraError.md) – A chunker needs a package extra that is not installed.
- [**Chunking**](rules/Chunking.md) – An ordered list of chunking rules and a fallback chunker.
- [**ChunkingError**](base/ChunkingError.md) – A chunker broke the chunk contract or failed to chunk a document.
- [**ChunkingRule**](rules/ChunkingRule.md) – A match and the chunker for the documents it matches.
- [**CodeChunker**](extras/CodeChunker.md) – Cuts source code along its syntax tree.
- [**DoclingChunker**](docling/DoclingChunker.md) – Split a parsed docling document with docling hybrid chunker.
- [**HeadingChunker**](heading/HeadingChunker.md) – Cuts a document into sections at its headings and packs them to a budget.
- [**NeuralChunker**](extras/NeuralChunker.md) – Cuts where a token classification model predicts a topic break.
- [**ParentChildChunker**](parent_child/ParentChildChunker.md) – Cuts a document into parent chunks and cuts each parent into child chunks.
- [**RecursiveChunker**](recursive/RecursiveChunker.md) – Splits on paragraph, sentence and word boundaries, coarsest first.
- [**RuleMatch**](rules/RuleMatch.md) – The documents a rule applies to.
- [**SemanticChunker**](extras/SemanticChunker.md) – Cuts where the meaning of neighbouring sentences changes.
- [**SentenceChunker**](sentence/SentenceChunker.md) – Packs whole sentences into chunks of at most `chunk_size` tokens.
- [**SplitLevel**](recursive/SplitLevel.md) – One level of recursive split rules.
- [**TokenChunker**](token/TokenChunker.md) – Cuts the text into windows of `chunk_size` tokens.
- [**TurnWindowChunker**](turns/TurnWindowChunker.md) – Packs whole chat turns into windows of at most `chunk_size` tokens.

**Attributes:**

- [**DEFAULT_CHUNKING**](rules/DEFAULT_CHUNKING.md) – The preset that `Graph` uses: `docling` loads go to `DoclingChunker`.
