---
title: agrag.chunking
sidebar_position: 3
---

## `agrag.chunking` \{#agrag-chunking}

Chunking: how a Document becomes Chunks.

A `Chunker` splits one document. A `Chunking` holds the rules that pick a chunker
for each document, and `DEFAULT_CHUNKING` is the preset that `Graph` uses.

**Modules:**

- [**base**](#agrag-chunking-base) – The Chunker contract: how a Document becomes Chunks, and how that is recorded.
- [**docling**](#agrag-chunking-docling) – Docling-native chunking.
- [**extras**](#agrag-chunking-extras) – Opt-in chunkers that need a package extra: semantic, neural and code.
- [**heading**](#agrag-chunking-heading) – The heading-aware strategy: sections packed to a token budget.
- [**parent_child**](#agrag-chunking-parent_child) – The parent-child strategy: large parents to extract, small children to search.
- [**recursive**](#agrag-chunking-recursive) – The recursive strategy: split on the coarsest delimiter that fits the budget.
- [**rules**](#agrag-chunking-rules) – Chunking rules: which chunker a document gets, as data.
- [**sentence**](#agrag-chunking-sentence) – The sentence strategy: whole sentences packed up to a token budget.
- [**token**](#agrag-chunking-token) – The token strategy: fixed-size windows of tokens, with optional overlap.
- [**turns**](#agrag-chunking-turns) – The turn-window strategy: whole chat turns packed to a token budget.

**Classes:**

- [**Chunker**](#agrag-chunking-Chunker) – Splits one Document into Chunks and builds their provenance.
- [**ChunkerMissingExtraError**](#agrag-chunking-ChunkerMissingExtraError) – A chunker needs a package extra that is not installed.
- [**Chunking**](#agrag-chunking-Chunking) – An ordered list of chunking rules and a fallback chunker.
- [**ChunkingError**](#agrag-chunking-ChunkingError) – A chunker broke the chunk contract or could not chunk a document.
- [**ChunkingRule**](#agrag-chunking-ChunkingRule) – A match and the chunker for the documents it matches.
- [**CodeChunker**](#agrag-chunking-CodeChunker) – Cuts source code along its syntax tree.
- [**DoclingChunker**](#agrag-chunking-DoclingChunker) – Splits a parsed docling document with docling's hybrid chunker.
- [**HeadingChunker**](#agrag-chunking-HeadingChunker) – Cuts a document into sections at its headings and packs them to a budget.
- [**NeuralChunker**](#agrag-chunking-NeuralChunker) – Cuts where a token classification model predicts a topic break.
- [**ParentChildChunker**](#agrag-chunking-ParentChildChunker) – Cuts a document into parent chunks and cuts each parent into child chunks.
- [**RecursiveChunker**](#agrag-chunking-RecursiveChunker) – Splits on paragraph, sentence and word boundaries, coarsest first.
- [**RuleMatch**](#agrag-chunking-RuleMatch) – The documents a rule applies to.
- [**SemanticChunker**](#agrag-chunking-SemanticChunker) – Cuts where the meaning of neighbouring sentences changes.
- [**SentenceChunker**](#agrag-chunking-SentenceChunker) – Packs whole sentences into chunks of at most `chunk_size` tokens.
- [**SplitLevel**](#agrag-chunking-SplitLevel) – One level of recursive split rules.
- [**TokenChunker**](#agrag-chunking-TokenChunker) – Cuts the text into windows of `chunk_size` tokens.
- [**TurnWindowChunker**](#agrag-chunking-TurnWindowChunker) – Packs whole chat turns into windows of at most `chunk_size` tokens.

**Attributes:**

- [**DEFAULT_CHUNKING**](#agrag-chunking-DEFAULT_CHUNKING) –

### `agrag.chunking.Chunker` \{#agrag-chunking-Chunker}

Bases: <code>BaseModel</code>, <code>ABC</code>

Splits one Document into Chunks and builds their provenance.

A chunker is plain data: its fields are its settings. `settings()` lists them
and `fingerprint()` hashes them, so two chunkers with equal settings have equal
fingerprints. Subclasses implement `strategy` and `_split`. `chunk()`
checks what `_split` returns and records the chunker on every chunk.

**Functions:**

- [**chunk**](#agrag-chunking-Chunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-Chunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-Chunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-Chunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-Chunker-settings) – Return the strategy name and every setting as JSON-safe data.

**Attributes:**

- [**model_config**](#agrag-chunking-Chunker-model_config) –
- [**strategy**](#agrag-chunking-Chunker-strategy) (<code>str</code>) – The stable name of this strategy, for example `"recursive"`.

#### `agrag.chunking.Chunker.chunk` \{#agrag-chunking-Chunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.Chunker.fingerprint` \{#agrag-chunking-Chunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.Chunker.model_config` \{#agrag-chunking-Chunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.Chunker.model_copy` \{#agrag-chunking-Chunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.Chunker.model_post_init` \{#agrag-chunking-Chunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

#### `agrag.chunking.Chunker.settings` \{#agrag-chunking-Chunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.Chunker.strategy` \{#agrag-chunking-Chunker-strategy}

```python
strategy: str
```

The stable name of this strategy, for example `"recursive"`.

### `agrag.chunking.ChunkerMissingExtraError` \{#agrag-chunking-ChunkerMissingExtraError}

```python
ChunkerMissingExtraError(strategy:str, extra:str) -> None
```

Bases: <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code>

A chunker needs a package extra that is not installed.

**Attributes:**

- [**strategy**](#agrag-chunking-ChunkerMissingExtraError-strategy) – The strategy name that needs the extra.
- [**extra**](#agrag-chunking-ChunkerMissingExtraError-extra) – The package extra to install.

#### `agrag.chunking.ChunkerMissingExtraError.extra` \{#agrag-chunking-ChunkerMissingExtraError-extra}

```python
extra = extra
```

#### `agrag.chunking.ChunkerMissingExtraError.strategy` \{#agrag-chunking-ChunkerMissingExtraError-strategy}

```python
strategy = strategy
```

### `agrag.chunking.Chunking` \{#agrag-chunking-Chunking}

Bases: <code>BaseModel</code>

An ordered list of chunking rules and a fallback chunker.

The first rule that matches a document picks its chunker. A document that no
rule matches gets `fallback`.

**Attributes:**

- [**rules**](#agrag-chunking-Chunking-rules) (<code>tuple\[[ChunkingRule](#agrag-chunking-rules-ChunkingRule), ...\]</code>) – The rules, most specific first.
- [**fallback**](#agrag-chunking-Chunking-fallback) (<code>SerializeAsAny\[[Chunker](#agrag-chunking-base-Chunker)\]</code>) – The chunker for documents that no rule matches.

**Functions:**

- [**fingerprint**](#agrag-chunking-Chunking-fingerprint) – Return a hash of every rule match and every chunker setting.
- [**select**](#agrag-chunking-Chunking-select) – Pick the chunker for a document.

#### `agrag.chunking.Chunking.fallback` \{#agrag-chunking-Chunking-fallback}

```python
fallback: SerializeAsAny[Chunker]
```

#### `agrag.chunking.Chunking.fingerprint` \{#agrag-chunking-Chunking-fingerprint}

```python
fingerprint() -> str
```

Return a hash of every rule match and every chunker setting.

#### `agrag.chunking.Chunking.model_config` \{#agrag-chunking-Chunking-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.Chunking.rules` \{#agrag-chunking-Chunking-rules}

```python
rules: tuple[ChunkingRule, ...] = ()
```

#### `agrag.chunking.Chunking.select` \{#agrag-chunking-Chunking-select}

```python
select(document:Document) -> tuple[int | None, Chunker]
```

Pick the chunker for a document.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to chunk.

**Returns:**

- <code>int | None</code> – The index of the first matching rule and its chunker, or `None` and
- <code>[Chunker](#agrag-chunking-base-Chunker)</code> – the fallback when no rule matches.

### `agrag.chunking.ChunkingError` \{#agrag-chunking-ChunkingError}

Bases: <code>Exception</code>

A chunker broke the chunk contract or could not chunk a document.

### `agrag.chunking.ChunkingRule` \{#agrag-chunking-ChunkingRule}

Bases: <code>BaseModel</code>

A match and the chunker for the documents it matches.

**Attributes:**

- [**match**](#agrag-chunking-ChunkingRule-match) (<code>[RuleMatch](#agrag-chunking-rules-RuleMatch)</code>) – The documents this rule applies to.
- [**chunker**](#agrag-chunking-ChunkingRule-chunker) (<code>SerializeAsAny\[[Chunker](#agrag-chunking-base-Chunker)\]</code>) – The chunker those documents get.

#### `agrag.chunking.ChunkingRule.chunker` \{#agrag-chunking-ChunkingRule-chunker}

```python
chunker: SerializeAsAny[Chunker]
```

#### `agrag.chunking.ChunkingRule.match` \{#agrag-chunking-ChunkingRule-match}

```python
match: RuleMatch
```

#### `agrag.chunking.ChunkingRule.model_config` \{#agrag-chunking-ChunkingRule-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

### `agrag.chunking.CodeChunker` \{#agrag-chunking-CodeChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts source code along its syntax tree.

Needs the `chunk-code` extra. The parser reports byte offsets, and this
chunker converts them to character offsets, so chunk text equals the source
slice for non-ASCII code too.

**Attributes:**

- [**language**](#agrag-chunking-CodeChunker-language) (<code>str</code>) – A tree-sitter language name, or `"auto"` to detect it.
- [**chunk_size**](#agrag-chunking-CodeChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**tokenizer**](#agrag-chunking-CodeChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-CodeChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-CodeChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-CodeChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-CodeChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-CodeChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-CodeChunker-spans) – Return character spans, converted from the parser's byte spans.

#### `agrag.chunking.CodeChunker.chunk` \{#agrag-chunking-CodeChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.CodeChunker.chunk_size` \{#agrag-chunking-CodeChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

#### `agrag.chunking.CodeChunker.fingerprint` \{#agrag-chunking-CodeChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.CodeChunker.language` \{#agrag-chunking-CodeChunker-language}

```python
language: str = 'auto'
```

#### `agrag.chunking.CodeChunker.model_config` \{#agrag-chunking-CodeChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.CodeChunker.model_copy` \{#agrag-chunking-CodeChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.CodeChunker.model_post_init` \{#agrag-chunking-CodeChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

#### `agrag.chunking.CodeChunker.settings` \{#agrag-chunking-CodeChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.CodeChunker.spans` \{#agrag-chunking-CodeChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return character spans, converted from the parser's byte spans.

#### `agrag.chunking.CodeChunker.strategy` \{#agrag-chunking-CodeChunker-strategy}

```python
strategy: str
```

The strategy name, `"code"`.

#### `agrag.chunking.CodeChunker.tokenizer` \{#agrag-chunking-CodeChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.DEFAULT_CHUNKING` \{#agrag-chunking-DEFAULT_CHUNKING}

```python
DEFAULT_CHUNKING = Chunking(rules=(ChunkingRule(match=RuleMatch(loader_names=['docling']), chunker=DoclingChunker()),), fallback=RecursiveChunker(tokenizer='character', chunk_size=1024, min_characters_per_chunk=24))
```

### `agrag.chunking.DoclingChunker` \{#agrag-chunking-DoclingChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

Splits a parsed docling document with docling's hybrid chunker.

The chunker reads the parsed document that the docling loader keeps in
`Document.metadata["_docling_document"]`. Each chunk has page provenance and
the headings above it in `heading_path`. The chunk text is the body without
headings, but headings count against the token budget. Chunk ids include the
fingerprint, so a re-chunk with new settings does not overwrite the old chunks.

**Attributes:**

- [**tokenizer**](#agrag-chunking-DoclingChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. A name with a slash is a Hugging
  Face model id, which needs the network the first time.
- [**max_tokens**](#agrag-chunking-DoclingChunker-max_tokens) (<code>int</code>) – The most tokens in a chunk, headings included.
- [**merge_peers**](#agrag-chunking-DoclingChunker-merge_peers) (<code>bool</code>) – Whether to merge small neighbours under the same headings.
- [**repeat_table_header**](#agrag-chunking-DoclingChunker-repeat_table_header) (<code>bool</code>) – Whether each chunk of a split table repeats its header.
- [**omit_header_on_overflow**](#agrag-chunking-DoclingChunker-omit_header_on_overflow) (<code>bool</code>) – Whether to drop headings from a chunk when they
  would not fit the budget.
- [**table_format**](#agrag-chunking-DoclingChunker-table_format) (<code>Literal['triplet', 'markdown']</code>) – `"triplet"` writes `row, column = value` text and
  `"markdown"` writes a pipe table.

**Functions:**

- [**chunk**](#agrag-chunking-DoclingChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-DoclingChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-DoclingChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-DoclingChunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-DoclingChunker-settings) – Return the strategy name and every setting as JSON-safe data.

#### `agrag.chunking.DoclingChunker.chunk` \{#agrag-chunking-DoclingChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.DoclingChunker.fingerprint` \{#agrag-chunking-DoclingChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.DoclingChunker.max_tokens` \{#agrag-chunking-DoclingChunker-max_tokens}

```python
max_tokens: int = Field(default=1024, gt=0)
```

#### `agrag.chunking.DoclingChunker.merge_peers` \{#agrag-chunking-DoclingChunker-merge_peers}

```python
merge_peers: bool = True
```

#### `agrag.chunking.DoclingChunker.model_config` \{#agrag-chunking-DoclingChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.DoclingChunker.model_copy` \{#agrag-chunking-DoclingChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.DoclingChunker.model_post_init` \{#agrag-chunking-DoclingChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

#### `agrag.chunking.DoclingChunker.omit_header_on_overflow` \{#agrag-chunking-DoclingChunker-omit_header_on_overflow}

```python
omit_header_on_overflow: bool = False
```

#### `agrag.chunking.DoclingChunker.repeat_table_header` \{#agrag-chunking-DoclingChunker-repeat_table_header}

```python
repeat_table_header: bool = True
```

#### `agrag.chunking.DoclingChunker.settings` \{#agrag-chunking-DoclingChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.DoclingChunker.strategy` \{#agrag-chunking-DoclingChunker-strategy}

```python
strategy: str
```

The strategy name, `"docling"`.

#### `agrag.chunking.DoclingChunker.table_format` \{#agrag-chunking-DoclingChunker-table_format}

```python
table_format: Literal['triplet', 'markdown'] = 'triplet'
```

#### `agrag.chunking.DoclingChunker.tokenizer` \{#agrag-chunking-DoclingChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.HeadingChunker` \{#agrag-chunking-HeadingChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

Cuts a document into sections at its headings and packs them to a budget.

The chunker reads `Document.heading_outline`. A heading of `split_level` or
higher (a level number at or below `split_level`) starts a new section, and no
chunk holds such a heading except at its start. A section within `chunk_size`
tokens is one chunk. A larger section is cut at its deeper headings and the
parts are packed to the budget. A part that is still too large goes to
`fallback`, and its chunks have the chunker name `heading:<fallback strategy>`. A document with no headings goes to `fallback` as a whole and its
chunks have the same name. Only the plain text loaders for Markdown and AsciiDoc
fill the outline.

**Attributes:**

- [**chunk_size**](#agrag-chunking-HeadingChunker-chunk_size) (<code>int</code>) – The most tokens in a chunk, counted with `tokenizer`. Tokens
  are counted for each part alone, so a packed chunk can be a few tokens
  over.
- [**split_level**](#agrag-chunking-HeadingChunker-split_level) (<code>int</code>) – The deepest heading level that starts a new section, from 1 to 6.
- [**tokenizer**](#agrag-chunking-HeadingChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**fallback**](#agrag-chunking-HeadingChunker-fallback) (<code>SerializeAsAny\[[SpanChunker](#agrag-chunking-base-SpanChunker)\]</code>) – The chunker for a part above the budget and for a document without
  headings.

**Functions:**

- [**chunk**](#agrag-chunking-HeadingChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-HeadingChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-HeadingChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-HeadingChunker-model_post_init) – Load the tokenizer once, so a bad name fails at construction.
- [**settings**](#agrag-chunking-HeadingChunker-settings) – Return the strategy name and every setting as JSON-safe data.

#### `agrag.chunking.HeadingChunker.chunk` \{#agrag-chunking-HeadingChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.HeadingChunker.chunk_size` \{#agrag-chunking-HeadingChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

#### `agrag.chunking.HeadingChunker.fallback` \{#agrag-chunking-HeadingChunker-fallback}

```python
fallback: SerializeAsAny[SpanChunker] = Field(default_factory=RecursiveChunker)
```

#### `agrag.chunking.HeadingChunker.fingerprint` \{#agrag-chunking-HeadingChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.HeadingChunker.model_config` \{#agrag-chunking-HeadingChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.HeadingChunker.model_copy` \{#agrag-chunking-HeadingChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.HeadingChunker.model_post_init` \{#agrag-chunking-HeadingChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Load the tokenizer once, so a bad name fails at construction.

#### `agrag.chunking.HeadingChunker.settings` \{#agrag-chunking-HeadingChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.HeadingChunker.split_level` \{#agrag-chunking-HeadingChunker-split_level}

```python
split_level: int = Field(default=2, ge=1, le=6)
```

#### `agrag.chunking.HeadingChunker.strategy` \{#agrag-chunking-HeadingChunker-strategy}

```python
strategy: str
```

The strategy name, `"heading"`.

#### `agrag.chunking.HeadingChunker.tokenizer` \{#agrag-chunking-HeadingChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.NeuralChunker` \{#agrag-chunking-NeuralChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts where a token classification model predicts a topic break.

Needs the `chunk-neural` extra. The first use downloads the model.

**Attributes:**

- [**model**](#agrag-chunking-NeuralChunker-model) (<code>str | None</code>) – The Hugging Face model id. `None` uses chonkie's default model.
- [**device_map**](#agrag-chunking-NeuralChunker-device_map) (<code>str</code>) – The device for the model, for example `"cpu"` or `"auto"`.
- [**min_characters_per_chunk**](#agrag-chunking-NeuralChunker-min_characters_per_chunk) (<code>int</code>) – The smallest chunk the splitter keeps apart.

**Functions:**

- [**chunk**](#agrag-chunking-NeuralChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-NeuralChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-NeuralChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-NeuralChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-NeuralChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-NeuralChunker-spans) – Return the character spans this strategy cuts text into.

#### `agrag.chunking.NeuralChunker.chunk` \{#agrag-chunking-NeuralChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.NeuralChunker.device_map` \{#agrag-chunking-NeuralChunker-device_map}

```python
device_map: str = 'cpu'
```

#### `agrag.chunking.NeuralChunker.fingerprint` \{#agrag-chunking-NeuralChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.NeuralChunker.min_characters_per_chunk` \{#agrag-chunking-NeuralChunker-min_characters_per_chunk}

```python
min_characters_per_chunk: int = Field(default=10, gt=0)
```

#### `agrag.chunking.NeuralChunker.model` \{#agrag-chunking-NeuralChunker-model}

```python
model: str | None = None
```

#### `agrag.chunking.NeuralChunker.model_config` \{#agrag-chunking-NeuralChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.NeuralChunker.model_copy` \{#agrag-chunking-NeuralChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.NeuralChunker.model_post_init` \{#agrag-chunking-NeuralChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

#### `agrag.chunking.NeuralChunker.settings` \{#agrag-chunking-NeuralChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.NeuralChunker.spans` \{#agrag-chunking-NeuralChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the character spans this strategy cuts text into.

**Raises:**

- <code>[ChunkerMissingExtraError](#agrag-chunking-base-ChunkerMissingExtraError)</code> – The package extra is not installed.

#### `agrag.chunking.NeuralChunker.strategy` \{#agrag-chunking-NeuralChunker-strategy}

```python
strategy: str
```

The strategy name, `"neural"`.

### `agrag.chunking.ParentChildChunker` \{#agrag-chunking-ParentChildChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

Cuts a document into parent chunks and cuts each parent into child chunks.

Extraction runs on the parents, which have `level=1`. The children have
`level=0` and a `parent_id`, and only the children are embedded and searched.
A search hit returns the child with its parent attached.

A child never crosses a parent boundary, because the child strategy cuts each
parent alone. Text of a parent that the child strategy leaves out gets a child of
its own, so all non-blank text can be found by search. A parent that the child
strategy leaves without any piece gets one child with the span of the parent.

The chunker returns all parents, then all children. Indexes count from 0 at each
level.

**Attributes:**

- [**parent**](#agrag-chunking-ParentChildChunker-parent) (<code>SerializeAsAny\[[SpanChunker](#agrag-chunking-base-SpanChunker)\]</code>) – The strategy that cuts the document into parents.
- [**child**](#agrag-chunking-ParentChildChunker-child) (<code>SerializeAsAny\[[SpanChunker](#agrag-chunking-base-SpanChunker)\]</code>) – The strategy that cuts each parent into children.

**Functions:**

- [**chunk**](#agrag-chunking-ParentChildChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-ParentChildChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-ParentChildChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-ParentChildChunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-ParentChildChunker-settings) – Return the strategy name and every setting as JSON-safe data.

#### `agrag.chunking.ParentChildChunker.child` \{#agrag-chunking-ParentChildChunker-child}

```python
child: SerializeAsAny[SpanChunker] = Field(default_factory=_default_child)
```

#### `agrag.chunking.ParentChildChunker.chunk` \{#agrag-chunking-ParentChildChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.ParentChildChunker.fingerprint` \{#agrag-chunking-ParentChildChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.ParentChildChunker.model_config` \{#agrag-chunking-ParentChildChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.ParentChildChunker.model_copy` \{#agrag-chunking-ParentChildChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.ParentChildChunker.model_post_init` \{#agrag-chunking-ParentChildChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

#### `agrag.chunking.ParentChildChunker.parent` \{#agrag-chunking-ParentChildChunker-parent}

```python
parent: SerializeAsAny[SpanChunker] = Field(default_factory=_default_parent)
```

#### `agrag.chunking.ParentChildChunker.settings` \{#agrag-chunking-ParentChildChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.ParentChildChunker.strategy` \{#agrag-chunking-ParentChildChunker-strategy}

```python
strategy: str
```

The strategy name, `"parent-child"`.

### `agrag.chunking.RecursiveChunker` \{#agrag-chunking-RecursiveChunker}

Bases: <code>[SpanChunker](#agrag-chunking-base-SpanChunker)</code>

Splits on paragraph, sentence and word boundaries, coarsest first.

**Attributes:**

- [**chunk_size**](#agrag-chunking-RecursiveChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**tokenizer**](#agrag-chunking-RecursiveChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**min_characters_per_chunk**](#agrag-chunking-RecursiveChunker-min_characters_per_chunk) (<code>int</code>) – The smallest piece the splitter keeps apart.
- [**levels**](#agrag-chunking-RecursiveChunker-levels) (<code>tuple\[[SplitLevel](#agrag-chunking-recursive-SplitLevel), ...\] | None</code>) – The split levels, coarsest first. `None` uses the default levels
  (paragraphs, sentences, punctuation, words, characters).

**Functions:**

- [**chunk**](#agrag-chunking-RecursiveChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-RecursiveChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-RecursiveChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-RecursiveChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-RecursiveChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-RecursiveChunker-spans) – Return the half-open character spans this strategy cuts text into.

#### `agrag.chunking.RecursiveChunker.chunk` \{#agrag-chunking-RecursiveChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.RecursiveChunker.chunk_size` \{#agrag-chunking-RecursiveChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

#### `agrag.chunking.RecursiveChunker.fingerprint` \{#agrag-chunking-RecursiveChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.RecursiveChunker.levels` \{#agrag-chunking-RecursiveChunker-levels}

```python
levels: tuple[SplitLevel, ...] | None = None
```

#### `agrag.chunking.RecursiveChunker.min_characters_per_chunk` \{#agrag-chunking-RecursiveChunker-min_characters_per_chunk}

```python
min_characters_per_chunk: int = Field(default=24, gt=0)
```

#### `agrag.chunking.RecursiveChunker.model_config` \{#agrag-chunking-RecursiveChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.RecursiveChunker.model_copy` \{#agrag-chunking-RecursiveChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.RecursiveChunker.model_post_init` \{#agrag-chunking-RecursiveChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

#### `agrag.chunking.RecursiveChunker.settings` \{#agrag-chunking-RecursiveChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.RecursiveChunker.spans` \{#agrag-chunking-RecursiveChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the half-open character spans this strategy cuts text into.

A cut inside a character that a tokenizer splits into several tokens makes
an empty piece. This method drops empty pieces, and no text is lost with them.

**Parameters:**

- **text** (<code>str</code>) – The text to cut.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The spans, in order, all non-empty.

#### `agrag.chunking.RecursiveChunker.strategy` \{#agrag-chunking-RecursiveChunker-strategy}

```python
strategy: str
```

The strategy name, `"recursive"`.

#### `agrag.chunking.RecursiveChunker.tokenizer` \{#agrag-chunking-RecursiveChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.RuleMatch` \{#agrag-chunking-RuleMatch}

Bases: <code>BaseModel</code>

The documents a rule applies to.

Every key is optional and a key left as `None` matches any value. Keys combine
with AND. A value in a list key matches if it equals any item of the list.

**Attributes:**

- [**loader_names**](#agrag-chunking-RuleMatch-loader_names) (<code>tuple\[str, ...\] | None</code>) – Match `Document.loader_name`.
- [**source_formats**](#agrag-chunking-RuleMatch-source_formats) (<code>tuple\[[SourceFormat](common.md#agrag-common-data_models-document-SourceFormat), ...\] | None</code>) – Match `Document.source_format`.
- [**families**](#agrag-chunking-RuleMatch-families) (<code>tuple\[[DocumentFamily](common.md#agrag-common-data_models-document-DocumentFamily), ...\] | None</code>) – Match `Document.family`.
- [**uri_glob**](#agrag-chunking-RuleMatch-uri_glob) (<code>str | None</code>) – Match `Document.uri` against this `fnmatch` pattern. Case
  sensitive.

**Functions:**

- [**matches**](#agrag-chunking-RuleMatch-matches) – Return whether every set key matches the document.

#### `agrag.chunking.RuleMatch.families` \{#agrag-chunking-RuleMatch-families}

```python
families: tuple[DocumentFamily, ...] | None = None
```

#### `agrag.chunking.RuleMatch.loader_names` \{#agrag-chunking-RuleMatch-loader_names}

```python
loader_names: tuple[str, ...] | None = None
```

#### `agrag.chunking.RuleMatch.matches` \{#agrag-chunking-RuleMatch-matches}

```python
matches(document:Document) -> bool
```

Return whether every set key matches the document.

#### `agrag.chunking.RuleMatch.model_config` \{#agrag-chunking-RuleMatch-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.RuleMatch.source_formats` \{#agrag-chunking-RuleMatch-source_formats}

```python
source_formats: tuple[SourceFormat, ...] | None = None
```

#### `agrag.chunking.RuleMatch.uri_glob` \{#agrag-chunking-RuleMatch-uri_glob}

```python
uri_glob: str | None = None
```

### `agrag.chunking.SemanticChunker` \{#agrag-chunking-SemanticChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts where the meaning of neighbouring sentences changes.

Needs the `chunk-semantic` extra. The chunker embeds sentences with a small
static model and cuts where similarity drops below `threshold`.

**Attributes:**

- [**embedding_model**](#agrag-chunking-SemanticChunker-embedding_model) (<code>str</code>) – The model that embeds sentences. The first use downloads it.
- [**threshold**](#agrag-chunking-SemanticChunker-threshold) (<code>float</code>) – The similarity below which a new chunk starts, from 0 to 1.
- [**chunk_size**](#agrag-chunking-SemanticChunker-chunk_size) (<code>int</code>) – The largest chunk size, as chonkie's semantic chunker counts it.
- [**similarity_window**](#agrag-chunking-SemanticChunker-similarity_window) (<code>int</code>) – The number of sentences that a similarity looks across.

**Functions:**

- [**chunk**](#agrag-chunking-SemanticChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-SemanticChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-SemanticChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-SemanticChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-SemanticChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-SemanticChunker-spans) – Return the character spans this strategy cuts text into.

#### `agrag.chunking.SemanticChunker.chunk` \{#agrag-chunking-SemanticChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.SemanticChunker.chunk_size` \{#agrag-chunking-SemanticChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

#### `agrag.chunking.SemanticChunker.embedding_model` \{#agrag-chunking-SemanticChunker-embedding_model}

```python
embedding_model: str = 'minishlab/potion-base-32M'
```

#### `agrag.chunking.SemanticChunker.fingerprint` \{#agrag-chunking-SemanticChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.SemanticChunker.model_config` \{#agrag-chunking-SemanticChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.SemanticChunker.model_copy` \{#agrag-chunking-SemanticChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.SemanticChunker.model_post_init` \{#agrag-chunking-SemanticChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

#### `agrag.chunking.SemanticChunker.settings` \{#agrag-chunking-SemanticChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.SemanticChunker.similarity_window` \{#agrag-chunking-SemanticChunker-similarity_window}

```python
similarity_window: int = Field(default=3, gt=0)
```

#### `agrag.chunking.SemanticChunker.spans` \{#agrag-chunking-SemanticChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the character spans this strategy cuts text into.

**Raises:**

- <code>[ChunkerMissingExtraError](#agrag-chunking-base-ChunkerMissingExtraError)</code> – The package extra is not installed.

#### `agrag.chunking.SemanticChunker.strategy` \{#agrag-chunking-SemanticChunker-strategy}

```python
strategy: str
```

The strategy name, `"semantic"`.

#### `agrag.chunking.SemanticChunker.threshold` \{#agrag-chunking-SemanticChunker-threshold}

```python
threshold: float = Field(default=0.8, gt=0, le=1)
```

### `agrag.chunking.SentenceChunker` \{#agrag-chunking-SentenceChunker}

Bases: <code>[SpanChunker](#agrag-chunking-base-SpanChunker)</code>

Packs whole sentences into chunks of at most `chunk_size` tokens.

A single sentence longer than `chunk_size` stays whole, so a chunk can be
larger than the budget when the text has a very long sentence.

**Attributes:**

- [**chunk_size**](#agrag-chunking-SentenceChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**chunk_overlap**](#agrag-chunking-SentenceChunker-chunk_overlap) (<code>int</code>) – The overlap between neighbours, in tokens. Each chunk keeps
  its exact span in the document.
- [**min_sentences_per_chunk**](#agrag-chunking-SentenceChunker-min_sentences_per_chunk) (<code>int</code>) – The fewest sentences in a chunk.
- [**min_characters_per_sentence**](#agrag-chunking-SentenceChunker-min_characters_per_sentence) (<code>int</code>) – The shortest text that counts as a sentence.
- [**tokenizer**](#agrag-chunking-SentenceChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-SentenceChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-SentenceChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-SentenceChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-SentenceChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-SentenceChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-SentenceChunker-spans) – Return the half-open character spans this strategy cuts text into.

#### `agrag.chunking.SentenceChunker.chunk` \{#agrag-chunking-SentenceChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.SentenceChunker.chunk_overlap` \{#agrag-chunking-SentenceChunker-chunk_overlap}

```python
chunk_overlap: int = Field(default=0, ge=0)
```

#### `agrag.chunking.SentenceChunker.chunk_size` \{#agrag-chunking-SentenceChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

#### `agrag.chunking.SentenceChunker.fingerprint` \{#agrag-chunking-SentenceChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.SentenceChunker.min_characters_per_sentence` \{#agrag-chunking-SentenceChunker-min_characters_per_sentence}

```python
min_characters_per_sentence: int = Field(default=12, gt=0)
```

#### `agrag.chunking.SentenceChunker.min_sentences_per_chunk` \{#agrag-chunking-SentenceChunker-min_sentences_per_chunk}

```python
min_sentences_per_chunk: int = Field(default=1, gt=0)
```

#### `agrag.chunking.SentenceChunker.model_config` \{#agrag-chunking-SentenceChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.SentenceChunker.model_copy` \{#agrag-chunking-SentenceChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.SentenceChunker.model_post_init` \{#agrag-chunking-SentenceChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

#### `agrag.chunking.SentenceChunker.settings` \{#agrag-chunking-SentenceChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.SentenceChunker.spans` \{#agrag-chunking-SentenceChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the half-open character spans this strategy cuts text into.

A cut inside a character that a tokenizer splits into several tokens makes
an empty piece. This method drops empty pieces, and no text is lost with them.

**Parameters:**

- **text** (<code>str</code>) – The text to cut.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The spans, in order, all non-empty.

#### `agrag.chunking.SentenceChunker.strategy` \{#agrag-chunking-SentenceChunker-strategy}

```python
strategy: str
```

The strategy name, `"sentence"`.

#### `agrag.chunking.SentenceChunker.tokenizer` \{#agrag-chunking-SentenceChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.SplitLevel` \{#agrag-chunking-SplitLevel}

Bases: <code>BaseModel</code>

One level of recursive split rules.

**Attributes:**

- [**delimiters**](#agrag-chunking-SplitLevel-delimiters) (<code>tuple\[str, ...\] | None</code>) – The strings to split on at this level. `None` means none.
- [**whitespace**](#agrag-chunking-SplitLevel-whitespace) (<code>bool</code>) – Whether to split on whitespace at this level.
- [**include_delim**](#agrag-chunking-SplitLevel-include_delim) (<code>Literal['prev', 'next'] | None</code>) – Whether a delimiter stays with the previous piece, the next
  piece, or is dropped.

#### `agrag.chunking.SplitLevel.delimiters` \{#agrag-chunking-SplitLevel-delimiters}

```python
delimiters: tuple[str, ...] | None = None
```

#### `agrag.chunking.SplitLevel.include_delim` \{#agrag-chunking-SplitLevel-include_delim}

```python
include_delim: Literal['prev', 'next'] | None = 'prev'
```

#### `agrag.chunking.SplitLevel.model_config` \{#agrag-chunking-SplitLevel-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.SplitLevel.whitespace` \{#agrag-chunking-SplitLevel-whitespace}

```python
whitespace: bool = False
```

### `agrag.chunking.TokenChunker` \{#agrag-chunking-TokenChunker}

Bases: <code>[SpanChunker](#agrag-chunking-base-SpanChunker)</code>

Cuts the text into windows of `chunk_size` tokens.

Neighbouring chunks overlap when `chunk_overlap` is set, and each chunk keeps
its exact span in the document.

**Attributes:**

- [**chunk_size**](#agrag-chunking-TokenChunker-chunk_size) (<code>int</code>) – The window size, counted with `tokenizer`.
- [**chunk_overlap**](#agrag-chunking-TokenChunker-chunk_overlap) (<code>int | float</code>) – The overlap between neighbours. An int counts tokens. A float
  from 0 up to 1 is a share of `chunk_size`.
- [**tokenizer**](#agrag-chunking-TokenChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-TokenChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-TokenChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-TokenChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-TokenChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-TokenChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-TokenChunker-spans) – Return the half-open character spans this strategy cuts text into.

#### `agrag.chunking.TokenChunker.chunk` \{#agrag-chunking-TokenChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.TokenChunker.chunk_overlap` \{#agrag-chunking-TokenChunker-chunk_overlap}

```python
chunk_overlap: int | float = Field(default=0, ge=0)
```

#### `agrag.chunking.TokenChunker.chunk_size` \{#agrag-chunking-TokenChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

#### `agrag.chunking.TokenChunker.fingerprint` \{#agrag-chunking-TokenChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.TokenChunker.model_config` \{#agrag-chunking-TokenChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.TokenChunker.model_copy` \{#agrag-chunking-TokenChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.TokenChunker.model_post_init` \{#agrag-chunking-TokenChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

#### `agrag.chunking.TokenChunker.settings` \{#agrag-chunking-TokenChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.TokenChunker.spans` \{#agrag-chunking-TokenChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the half-open character spans this strategy cuts text into.

A cut inside a character that a tokenizer splits into several tokens makes
an empty piece. This method drops empty pieces, and no text is lost with them.

**Parameters:**

- **text** (<code>str</code>) – The text to cut.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The spans, in order, all non-empty.

#### `agrag.chunking.TokenChunker.strategy` \{#agrag-chunking-TokenChunker-strategy}

```python
strategy: str
```

The strategy name, `"token"`.

#### `agrag.chunking.TokenChunker.tokenizer` \{#agrag-chunking-TokenChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.TurnWindowChunker` \{#agrag-chunking-TurnWindowChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

Packs whole chat turns into windows of at most `chunk_size` tokens.

The chunker reads `Document.turns`. A window holds one or more whole turns, and
a chunk boundary never falls inside a turn. Tokens are counted for each turn
alone, so the separators between turns are not part of the count. Text before
the first turn joins the first window, and text after a turn joins the window
that holds that turn.

A turn above the budget is split by `fallback`, and its chunks have the
chunker name `turn-window:<fallback strategy>`. A document without turns is
split by `fallback` as a whole and its chunks have the same name.

**Attributes:**

- [**chunk_size**](#agrag-chunking-TurnWindowChunker-chunk_size) (<code>int</code>) – The most tokens in a window, counted with `tokenizer`.
- [**turn_overlap**](#agrag-chunking-TurnWindowChunker-turn_overlap) (<code>int</code>) – The number of turns that a window repeats from the window
  before it. A window always moves on by at least one turn.
- [**tokenizer**](#agrag-chunking-TurnWindowChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**fallback**](#agrag-chunking-TurnWindowChunker-fallback) (<code>SerializeAsAny\[[SpanChunker](#agrag-chunking-base-SpanChunker)\]</code>) – The chunker for a turn above the budget and for a document without
  turns.

**Functions:**

- [**chunk**](#agrag-chunking-TurnWindowChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-TurnWindowChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-TurnWindowChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-TurnWindowChunker-model_post_init) – Load the tokenizer once, so a bad name fails at construction.
- [**settings**](#agrag-chunking-TurnWindowChunker-settings) – Return the strategy name and every setting as JSON-safe data.

#### `agrag.chunking.TurnWindowChunker.chunk` \{#agrag-chunking-TurnWindowChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

#### `agrag.chunking.TurnWindowChunker.chunk_size` \{#agrag-chunking-TurnWindowChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

#### `agrag.chunking.TurnWindowChunker.fallback` \{#agrag-chunking-TurnWindowChunker-fallback}

```python
fallback: SerializeAsAny[SpanChunker] = Field(default_factory=RecursiveChunker)
```

#### `agrag.chunking.TurnWindowChunker.fingerprint` \{#agrag-chunking-TurnWindowChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

#### `agrag.chunking.TurnWindowChunker.model_config` \{#agrag-chunking-TurnWindowChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.TurnWindowChunker.model_copy` \{#agrag-chunking-TurnWindowChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

#### `agrag.chunking.TurnWindowChunker.model_post_init` \{#agrag-chunking-TurnWindowChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Load the tokenizer once, so a bad name fails at construction.

#### `agrag.chunking.TurnWindowChunker.settings` \{#agrag-chunking-TurnWindowChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

#### `agrag.chunking.TurnWindowChunker.strategy` \{#agrag-chunking-TurnWindowChunker-strategy}

```python
strategy: str
```

The strategy name, `"turn-window"`.

#### `agrag.chunking.TurnWindowChunker.tokenizer` \{#agrag-chunking-TurnWindowChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

#### `agrag.chunking.TurnWindowChunker.turn_overlap` \{#agrag-chunking-TurnWindowChunker-turn_overlap}

```python
turn_overlap: int = Field(default=0, ge=0)
```

### `agrag.chunking.base` \{#agrag-chunking-base}

The Chunker contract: how a Document becomes Chunks, and how that is recorded.

**Classes:**

- [**Chunker**](#agrag-chunking-base-Chunker) – Splits one Document into Chunks and builds their provenance.
- [**ChunkerMissingExtraError**](#agrag-chunking-base-ChunkerMissingExtraError) – A chunker needs a package extra that is not installed.
- [**ChunkingError**](#agrag-chunking-base-ChunkingError) – A chunker broke the chunk contract or could not chunk a document.
- [**SpanChunker**](#agrag-chunking-base-SpanChunker) – A chunker that only decides where to cut; text and offsets come from the source.

**Functions:**

- [**fingerprint_of**](#agrag-chunking-base-fingerprint_of) – Return a short stable hash of a JSON-safe value.

**Attributes:**

- [**DEFAULT_TOKENIZER**](#agrag-chunking-base-DEFAULT_TOKENIZER) –

#### `agrag.chunking.base.Chunker` \{#agrag-chunking-base-Chunker}

Bases: <code>BaseModel</code>, <code>ABC</code>

Splits one Document into Chunks and builds their provenance.

A chunker is plain data: its fields are its settings. `settings()` lists them
and `fingerprint()` hashes them, so two chunkers with equal settings have equal
fingerprints. Subclasses implement `strategy` and `_split`. `chunk()`
checks what `_split` returns and records the chunker on every chunk.

**Functions:**

- [**chunk**](#agrag-chunking-base-Chunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-base-Chunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-base-Chunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-base-Chunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-base-Chunker-settings) – Return the strategy name and every setting as JSON-safe data.

**Attributes:**

- [**model_config**](#agrag-chunking-base-Chunker-model_config) –
- [**strategy**](#agrag-chunking-base-Chunker-strategy) (<code>str</code>) – The stable name of this strategy, for example `"recursive"`.

##### `agrag.chunking.base.Chunker.chunk` \{#agrag-chunking-base-Chunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.base.Chunker.fingerprint` \{#agrag-chunking-base-Chunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.base.Chunker.model_config` \{#agrag-chunking-base-Chunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.base.Chunker.model_copy` \{#agrag-chunking-base-Chunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.base.Chunker.model_post_init` \{#agrag-chunking-base-Chunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

##### `agrag.chunking.base.Chunker.settings` \{#agrag-chunking-base-Chunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.base.Chunker.strategy` \{#agrag-chunking-base-Chunker-strategy}

```python
strategy: str
```

The stable name of this strategy, for example `"recursive"`.

#### `agrag.chunking.base.ChunkerMissingExtraError` \{#agrag-chunking-base-ChunkerMissingExtraError}

```python
ChunkerMissingExtraError(strategy:str, extra:str) -> None
```

Bases: <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code>

A chunker needs a package extra that is not installed.

**Attributes:**

- [**strategy**](#agrag-chunking-base-ChunkerMissingExtraError-strategy) – The strategy name that needs the extra.
- [**extra**](#agrag-chunking-base-ChunkerMissingExtraError-extra) – The package extra to install.

##### `agrag.chunking.base.ChunkerMissingExtraError.extra` \{#agrag-chunking-base-ChunkerMissingExtraError-extra}

```python
extra = extra
```

##### `agrag.chunking.base.ChunkerMissingExtraError.strategy` \{#agrag-chunking-base-ChunkerMissingExtraError-strategy}

```python
strategy = strategy
```

#### `agrag.chunking.base.ChunkingError` \{#agrag-chunking-base-ChunkingError}

Bases: <code>Exception</code>

A chunker broke the chunk contract or could not chunk a document.

#### `agrag.chunking.base.DEFAULT_TOKENIZER` \{#agrag-chunking-base-DEFAULT_TOKENIZER}

```python
DEFAULT_TOKENIZER = 'o200k_base'
```

#### `agrag.chunking.base.SpanChunker` \{#agrag-chunking-base-SpanChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

A chunker that only decides where to cut; text and offsets come from the source.

Subclasses build an engine that returns objects with `start_index` and
`end_index` for a text. The chunk text is always a slice of the document text,
so a lossy tokenizer round trip cannot change it.

**Functions:**

- [**chunk**](#agrag-chunking-base-SpanChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-base-SpanChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-base-SpanChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-base-SpanChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-base-SpanChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-base-SpanChunker-spans) – Return the half-open character spans this strategy cuts text into.

**Attributes:**

- [**model_config**](#agrag-chunking-base-SpanChunker-model_config) –
- [**strategy**](#agrag-chunking-base-SpanChunker-strategy) (<code>str</code>) – The stable name of this strategy, for example `"recursive"`.

##### `agrag.chunking.base.SpanChunker.chunk` \{#agrag-chunking-base-SpanChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.base.SpanChunker.fingerprint` \{#agrag-chunking-base-SpanChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.base.SpanChunker.model_config` \{#agrag-chunking-base-SpanChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.base.SpanChunker.model_copy` \{#agrag-chunking-base-SpanChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.base.SpanChunker.model_post_init` \{#agrag-chunking-base-SpanChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

##### `agrag.chunking.base.SpanChunker.settings` \{#agrag-chunking-base-SpanChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.base.SpanChunker.spans` \{#agrag-chunking-base-SpanChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the half-open character spans this strategy cuts text into.

A cut inside a character that a tokenizer splits into several tokens makes
an empty piece. This method drops empty pieces, and no text is lost with them.

**Parameters:**

- **text** (<code>str</code>) – The text to cut.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The spans, in order, all non-empty.

##### `agrag.chunking.base.SpanChunker.strategy` \{#agrag-chunking-base-SpanChunker-strategy}

```python
strategy: str
```

The stable name of this strategy, for example `"recursive"`.

#### `agrag.chunking.base.fingerprint_of` \{#agrag-chunking-base-fingerprint_of}

```python
fingerprint_of(value:object) -> str
```

Return a short stable hash of a JSON-safe value.

**Parameters:**

- **value** (<code>object</code>) – Data made of dicts, lists, strings, numbers, booleans and `None`.

**Returns:**

- <code>str</code> – The first 16 hex characters of the SHA-256 of the canonical JSON.

### `agrag.chunking.docling` \{#agrag-chunking-docling}

Docling-native chunking.

This module wraps docling's `HybridChunker` to produce `Chunk` objects with
`PageProvenance`. It imports docling only when it chunks a document, so importing
this module does not require the `docling` extra.

**Classes:**

- [**DoclingChunker**](#agrag-chunking-docling-DoclingChunker) – Splits a parsed docling document with docling's hybrid chunker.

#### `agrag.chunking.docling.DoclingChunker` \{#agrag-chunking-docling-DoclingChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

Splits a parsed docling document with docling's hybrid chunker.

The chunker reads the parsed document that the docling loader keeps in
`Document.metadata["_docling_document"]`. Each chunk has page provenance and
the headings above it in `heading_path`. The chunk text is the body without
headings, but headings count against the token budget. Chunk ids include the
fingerprint, so a re-chunk with new settings does not overwrite the old chunks.

**Attributes:**

- [**tokenizer**](#agrag-chunking-docling-DoclingChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. A name with a slash is a Hugging
  Face model id, which needs the network the first time.
- [**max_tokens**](#agrag-chunking-docling-DoclingChunker-max_tokens) (<code>int</code>) – The most tokens in a chunk, headings included.
- [**merge_peers**](#agrag-chunking-docling-DoclingChunker-merge_peers) (<code>bool</code>) – Whether to merge small neighbours under the same headings.
- [**repeat_table_header**](#agrag-chunking-docling-DoclingChunker-repeat_table_header) (<code>bool</code>) – Whether each chunk of a split table repeats its header.
- [**omit_header_on_overflow**](#agrag-chunking-docling-DoclingChunker-omit_header_on_overflow) (<code>bool</code>) – Whether to drop headings from a chunk when they
  would not fit the budget.
- [**table_format**](#agrag-chunking-docling-DoclingChunker-table_format) (<code>Literal['triplet', 'markdown']</code>) – `"triplet"` writes `row, column = value` text and
  `"markdown"` writes a pipe table.

**Functions:**

- [**chunk**](#agrag-chunking-docling-DoclingChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-docling-DoclingChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-docling-DoclingChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-docling-DoclingChunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-docling-DoclingChunker-settings) – Return the strategy name and every setting as JSON-safe data.

##### `agrag.chunking.docling.DoclingChunker.chunk` \{#agrag-chunking-docling-DoclingChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.docling.DoclingChunker.fingerprint` \{#agrag-chunking-docling-DoclingChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.docling.DoclingChunker.max_tokens` \{#agrag-chunking-docling-DoclingChunker-max_tokens}

```python
max_tokens: int = Field(default=1024, gt=0)
```

##### `agrag.chunking.docling.DoclingChunker.merge_peers` \{#agrag-chunking-docling-DoclingChunker-merge_peers}

```python
merge_peers: bool = True
```

##### `agrag.chunking.docling.DoclingChunker.model_config` \{#agrag-chunking-docling-DoclingChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.docling.DoclingChunker.model_copy` \{#agrag-chunking-docling-DoclingChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.docling.DoclingChunker.model_post_init` \{#agrag-chunking-docling-DoclingChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

##### `agrag.chunking.docling.DoclingChunker.omit_header_on_overflow` \{#agrag-chunking-docling-DoclingChunker-omit_header_on_overflow}

```python
omit_header_on_overflow: bool = False
```

##### `agrag.chunking.docling.DoclingChunker.repeat_table_header` \{#agrag-chunking-docling-DoclingChunker-repeat_table_header}

```python
repeat_table_header: bool = True
```

##### `agrag.chunking.docling.DoclingChunker.settings` \{#agrag-chunking-docling-DoclingChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.docling.DoclingChunker.strategy` \{#agrag-chunking-docling-DoclingChunker-strategy}

```python
strategy: str
```

The strategy name, `"docling"`.

##### `agrag.chunking.docling.DoclingChunker.table_format` \{#agrag-chunking-docling-DoclingChunker-table_format}

```python
table_format: Literal['triplet', 'markdown'] = 'triplet'
```

##### `agrag.chunking.docling.DoclingChunker.tokenizer` \{#agrag-chunking-docling-DoclingChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.extras` \{#agrag-chunking-extras}

Opt-in chunkers that need a package extra: semantic, neural and code.

**Classes:**

- [**CodeChunker**](#agrag-chunking-extras-CodeChunker) – Cuts source code along its syntax tree.
- [**NeuralChunker**](#agrag-chunking-extras-NeuralChunker) – Cuts where a token classification model predicts a topic break.
- [**SemanticChunker**](#agrag-chunking-extras-SemanticChunker) – Cuts where the meaning of neighbouring sentences changes.

**Functions:**

- [**byte_spans_to_char_spans**](#agrag-chunking-extras-byte_spans_to_char_spans) – Convert UTF-8 byte spans of `text` to character spans.

#### `agrag.chunking.extras.CodeChunker` \{#agrag-chunking-extras-CodeChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts source code along its syntax tree.

Needs the `chunk-code` extra. The parser reports byte offsets, and this
chunker converts them to character offsets, so chunk text equals the source
slice for non-ASCII code too.

**Attributes:**

- [**language**](#agrag-chunking-extras-CodeChunker-language) (<code>str</code>) – A tree-sitter language name, or `"auto"` to detect it.
- [**chunk_size**](#agrag-chunking-extras-CodeChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**tokenizer**](#agrag-chunking-extras-CodeChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-extras-CodeChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-extras-CodeChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-extras-CodeChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-extras-CodeChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-extras-CodeChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-extras-CodeChunker-spans) – Return character spans, converted from the parser's byte spans.

##### `agrag.chunking.extras.CodeChunker.chunk` \{#agrag-chunking-extras-CodeChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.extras.CodeChunker.chunk_size` \{#agrag-chunking-extras-CodeChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

##### `agrag.chunking.extras.CodeChunker.fingerprint` \{#agrag-chunking-extras-CodeChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.extras.CodeChunker.language` \{#agrag-chunking-extras-CodeChunker-language}

```python
language: str = 'auto'
```

##### `agrag.chunking.extras.CodeChunker.model_config` \{#agrag-chunking-extras-CodeChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.extras.CodeChunker.model_copy` \{#agrag-chunking-extras-CodeChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.extras.CodeChunker.model_post_init` \{#agrag-chunking-extras-CodeChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

##### `agrag.chunking.extras.CodeChunker.settings` \{#agrag-chunking-extras-CodeChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.extras.CodeChunker.spans` \{#agrag-chunking-extras-CodeChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return character spans, converted from the parser's byte spans.

##### `agrag.chunking.extras.CodeChunker.strategy` \{#agrag-chunking-extras-CodeChunker-strategy}

```python
strategy: str
```

The strategy name, `"code"`.

##### `agrag.chunking.extras.CodeChunker.tokenizer` \{#agrag-chunking-extras-CodeChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

#### `agrag.chunking.extras.NeuralChunker` \{#agrag-chunking-extras-NeuralChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts where a token classification model predicts a topic break.

Needs the `chunk-neural` extra. The first use downloads the model.

**Attributes:**

- [**model**](#agrag-chunking-extras-NeuralChunker-model) (<code>str | None</code>) – The Hugging Face model id. `None` uses chonkie's default model.
- [**device_map**](#agrag-chunking-extras-NeuralChunker-device_map) (<code>str</code>) – The device for the model, for example `"cpu"` or `"auto"`.
- [**min_characters_per_chunk**](#agrag-chunking-extras-NeuralChunker-min_characters_per_chunk) (<code>int</code>) – The smallest chunk the splitter keeps apart.

**Functions:**

- [**chunk**](#agrag-chunking-extras-NeuralChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-extras-NeuralChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-extras-NeuralChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-extras-NeuralChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-extras-NeuralChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-extras-NeuralChunker-spans) – Return the character spans this strategy cuts text into.

##### `agrag.chunking.extras.NeuralChunker.chunk` \{#agrag-chunking-extras-NeuralChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.extras.NeuralChunker.device_map` \{#agrag-chunking-extras-NeuralChunker-device_map}

```python
device_map: str = 'cpu'
```

##### `agrag.chunking.extras.NeuralChunker.fingerprint` \{#agrag-chunking-extras-NeuralChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.extras.NeuralChunker.min_characters_per_chunk` \{#agrag-chunking-extras-NeuralChunker-min_characters_per_chunk}

```python
min_characters_per_chunk: int = Field(default=10, gt=0)
```

##### `agrag.chunking.extras.NeuralChunker.model` \{#agrag-chunking-extras-NeuralChunker-model}

```python
model: str | None = None
```

##### `agrag.chunking.extras.NeuralChunker.model_config` \{#agrag-chunking-extras-NeuralChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.extras.NeuralChunker.model_copy` \{#agrag-chunking-extras-NeuralChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.extras.NeuralChunker.model_post_init` \{#agrag-chunking-extras-NeuralChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

##### `agrag.chunking.extras.NeuralChunker.settings` \{#agrag-chunking-extras-NeuralChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.extras.NeuralChunker.spans` \{#agrag-chunking-extras-NeuralChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the character spans this strategy cuts text into.

**Raises:**

- <code>[ChunkerMissingExtraError](#agrag-chunking-base-ChunkerMissingExtraError)</code> – The package extra is not installed.

##### `agrag.chunking.extras.NeuralChunker.strategy` \{#agrag-chunking-extras-NeuralChunker-strategy}

```python
strategy: str
```

The strategy name, `"neural"`.

#### `agrag.chunking.extras.SemanticChunker` \{#agrag-chunking-extras-SemanticChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts where the meaning of neighbouring sentences changes.

Needs the `chunk-semantic` extra. The chunker embeds sentences with a small
static model and cuts where similarity drops below `threshold`.

**Attributes:**

- [**embedding_model**](#agrag-chunking-extras-SemanticChunker-embedding_model) (<code>str</code>) – The model that embeds sentences. The first use downloads it.
- [**threshold**](#agrag-chunking-extras-SemanticChunker-threshold) (<code>float</code>) – The similarity below which a new chunk starts, from 0 to 1.
- [**chunk_size**](#agrag-chunking-extras-SemanticChunker-chunk_size) (<code>int</code>) – The largest chunk size, as chonkie's semantic chunker counts it.
- [**similarity_window**](#agrag-chunking-extras-SemanticChunker-similarity_window) (<code>int</code>) – The number of sentences that a similarity looks across.

**Functions:**

- [**chunk**](#agrag-chunking-extras-SemanticChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-extras-SemanticChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-extras-SemanticChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-extras-SemanticChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-extras-SemanticChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-extras-SemanticChunker-spans) – Return the character spans this strategy cuts text into.

##### `agrag.chunking.extras.SemanticChunker.chunk` \{#agrag-chunking-extras-SemanticChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.extras.SemanticChunker.chunk_size` \{#agrag-chunking-extras-SemanticChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

##### `agrag.chunking.extras.SemanticChunker.embedding_model` \{#agrag-chunking-extras-SemanticChunker-embedding_model}

```python
embedding_model: str = 'minishlab/potion-base-32M'
```

##### `agrag.chunking.extras.SemanticChunker.fingerprint` \{#agrag-chunking-extras-SemanticChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.extras.SemanticChunker.model_config` \{#agrag-chunking-extras-SemanticChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.extras.SemanticChunker.model_copy` \{#agrag-chunking-extras-SemanticChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.extras.SemanticChunker.model_post_init` \{#agrag-chunking-extras-SemanticChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

##### `agrag.chunking.extras.SemanticChunker.settings` \{#agrag-chunking-extras-SemanticChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.extras.SemanticChunker.similarity_window` \{#agrag-chunking-extras-SemanticChunker-similarity_window}

```python
similarity_window: int = Field(default=3, gt=0)
```

##### `agrag.chunking.extras.SemanticChunker.spans` \{#agrag-chunking-extras-SemanticChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the character spans this strategy cuts text into.

**Raises:**

- <code>[ChunkerMissingExtraError](#agrag-chunking-base-ChunkerMissingExtraError)</code> – The package extra is not installed.

##### `agrag.chunking.extras.SemanticChunker.strategy` \{#agrag-chunking-extras-SemanticChunker-strategy}

```python
strategy: str
```

The strategy name, `"semantic"`.

##### `agrag.chunking.extras.SemanticChunker.threshold` \{#agrag-chunking-extras-SemanticChunker-threshold}

```python
threshold: float = Field(default=0.8, gt=0, le=1)
```

#### `agrag.chunking.extras.byte_spans_to_char_spans` \{#agrag-chunking-extras-byte_spans_to_char_spans}

```python
byte_spans_to_char_spans(text:str, spans:list[tuple[int, int]]) -> list[tuple[int, int]]
```

Convert UTF-8 byte spans of `text` to character spans.

**Parameters:**

- **text** (<code>str</code>) – The text the byte offsets index once encoded as UTF-8.
- **spans** (<code>list\[tuple\[int, int\]\]</code>) – Half-open byte spans.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The same spans as character offsets. ASCII text returns the spans as given.

### `agrag.chunking.heading` \{#agrag-chunking-heading}

The heading-aware strategy: sections packed to a token budget.

**Classes:**

- [**HeadingChunker**](#agrag-chunking-heading-HeadingChunker) – Cuts a document into sections at its headings and packs them to a budget.

#### `agrag.chunking.heading.HeadingChunker` \{#agrag-chunking-heading-HeadingChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

Cuts a document into sections at its headings and packs them to a budget.

The chunker reads `Document.heading_outline`. A heading of `split_level` or
higher (a level number at or below `split_level`) starts a new section, and no
chunk holds such a heading except at its start. A section within `chunk_size`
tokens is one chunk. A larger section is cut at its deeper headings and the
parts are packed to the budget. A part that is still too large goes to
`fallback`, and its chunks have the chunker name `heading:<fallback strategy>`. A document with no headings goes to `fallback` as a whole and its
chunks have the same name. Only the plain text loaders for Markdown and AsciiDoc
fill the outline.

**Attributes:**

- [**chunk_size**](#agrag-chunking-heading-HeadingChunker-chunk_size) (<code>int</code>) – The most tokens in a chunk, counted with `tokenizer`. Tokens
  are counted for each part alone, so a packed chunk can be a few tokens
  over.
- [**split_level**](#agrag-chunking-heading-HeadingChunker-split_level) (<code>int</code>) – The deepest heading level that starts a new section, from 1 to 6.
- [**tokenizer**](#agrag-chunking-heading-HeadingChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**fallback**](#agrag-chunking-heading-HeadingChunker-fallback) (<code>SerializeAsAny\[[SpanChunker](#agrag-chunking-base-SpanChunker)\]</code>) – The chunker for a part above the budget and for a document without
  headings.

**Functions:**

- [**chunk**](#agrag-chunking-heading-HeadingChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-heading-HeadingChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-heading-HeadingChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-heading-HeadingChunker-model_post_init) – Load the tokenizer once, so a bad name fails at construction.
- [**settings**](#agrag-chunking-heading-HeadingChunker-settings) – Return the strategy name and every setting as JSON-safe data.

##### `agrag.chunking.heading.HeadingChunker.chunk` \{#agrag-chunking-heading-HeadingChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.heading.HeadingChunker.chunk_size` \{#agrag-chunking-heading-HeadingChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

##### `agrag.chunking.heading.HeadingChunker.fallback` \{#agrag-chunking-heading-HeadingChunker-fallback}

```python
fallback: SerializeAsAny[SpanChunker] = Field(default_factory=RecursiveChunker)
```

##### `agrag.chunking.heading.HeadingChunker.fingerprint` \{#agrag-chunking-heading-HeadingChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.heading.HeadingChunker.model_config` \{#agrag-chunking-heading-HeadingChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.heading.HeadingChunker.model_copy` \{#agrag-chunking-heading-HeadingChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.heading.HeadingChunker.model_post_init` \{#agrag-chunking-heading-HeadingChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Load the tokenizer once, so a bad name fails at construction.

##### `agrag.chunking.heading.HeadingChunker.settings` \{#agrag-chunking-heading-HeadingChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.heading.HeadingChunker.split_level` \{#agrag-chunking-heading-HeadingChunker-split_level}

```python
split_level: int = Field(default=2, ge=1, le=6)
```

##### `agrag.chunking.heading.HeadingChunker.strategy` \{#agrag-chunking-heading-HeadingChunker-strategy}

```python
strategy: str
```

The strategy name, `"heading"`.

##### `agrag.chunking.heading.HeadingChunker.tokenizer` \{#agrag-chunking-heading-HeadingChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.parent_child` \{#agrag-chunking-parent_child}

The parent-child strategy: large parents to extract, small children to search.

**Classes:**

- [**ParentChildChunker**](#agrag-chunking-parent_child-ParentChildChunker) – Cuts a document into parent chunks and cuts each parent into child chunks.

#### `agrag.chunking.parent_child.ParentChildChunker` \{#agrag-chunking-parent_child-ParentChildChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

Cuts a document into parent chunks and cuts each parent into child chunks.

Extraction runs on the parents, which have `level=1`. The children have
`level=0` and a `parent_id`, and only the children are embedded and searched.
A search hit returns the child with its parent attached.

A child never crosses a parent boundary, because the child strategy cuts each
parent alone. Text of a parent that the child strategy leaves out gets a child of
its own, so all non-blank text can be found by search. A parent that the child
strategy leaves without any piece gets one child with the span of the parent.

The chunker returns all parents, then all children. Indexes count from 0 at each
level.

**Attributes:**

- [**parent**](#agrag-chunking-parent_child-ParentChildChunker-parent) (<code>SerializeAsAny\[[SpanChunker](#agrag-chunking-base-SpanChunker)\]</code>) – The strategy that cuts the document into parents.
- [**child**](#agrag-chunking-parent_child-ParentChildChunker-child) (<code>SerializeAsAny\[[SpanChunker](#agrag-chunking-base-SpanChunker)\]</code>) – The strategy that cuts each parent into children.

**Functions:**

- [**chunk**](#agrag-chunking-parent_child-ParentChildChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-parent_child-ParentChildChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-parent_child-ParentChildChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-parent_child-ParentChildChunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-parent_child-ParentChildChunker-settings) – Return the strategy name and every setting as JSON-safe data.

##### `agrag.chunking.parent_child.ParentChildChunker.child` \{#agrag-chunking-parent_child-ParentChildChunker-child}

```python
child: SerializeAsAny[SpanChunker] = Field(default_factory=_default_child)
```

##### `agrag.chunking.parent_child.ParentChildChunker.chunk` \{#agrag-chunking-parent_child-ParentChildChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.parent_child.ParentChildChunker.fingerprint` \{#agrag-chunking-parent_child-ParentChildChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.parent_child.ParentChildChunker.model_config` \{#agrag-chunking-parent_child-ParentChildChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.parent_child.ParentChildChunker.model_copy` \{#agrag-chunking-parent_child-ParentChildChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.parent_child.ParentChildChunker.model_post_init` \{#agrag-chunking-parent_child-ParentChildChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

##### `agrag.chunking.parent_child.ParentChildChunker.parent` \{#agrag-chunking-parent_child-ParentChildChunker-parent}

```python
parent: SerializeAsAny[SpanChunker] = Field(default_factory=_default_parent)
```

##### `agrag.chunking.parent_child.ParentChildChunker.settings` \{#agrag-chunking-parent_child-ParentChildChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.parent_child.ParentChildChunker.strategy` \{#agrag-chunking-parent_child-ParentChildChunker-strategy}

```python
strategy: str
```

The strategy name, `"parent-child"`.

### `agrag.chunking.recursive` \{#agrag-chunking-recursive}

The recursive strategy: split on the coarsest delimiter that fits the budget.

**Classes:**

- [**RecursiveChunker**](#agrag-chunking-recursive-RecursiveChunker) – Splits on paragraph, sentence and word boundaries, coarsest first.
- [**SplitLevel**](#agrag-chunking-recursive-SplitLevel) – One level of recursive split rules.

#### `agrag.chunking.recursive.RecursiveChunker` \{#agrag-chunking-recursive-RecursiveChunker}

Bases: <code>[SpanChunker](#agrag-chunking-base-SpanChunker)</code>

Splits on paragraph, sentence and word boundaries, coarsest first.

**Attributes:**

- [**chunk_size**](#agrag-chunking-recursive-RecursiveChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**tokenizer**](#agrag-chunking-recursive-RecursiveChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**min_characters_per_chunk**](#agrag-chunking-recursive-RecursiveChunker-min_characters_per_chunk) (<code>int</code>) – The smallest piece the splitter keeps apart.
- [**levels**](#agrag-chunking-recursive-RecursiveChunker-levels) (<code>tuple\[[SplitLevel](#agrag-chunking-recursive-SplitLevel), ...\] | None</code>) – The split levels, coarsest first. `None` uses the default levels
  (paragraphs, sentences, punctuation, words, characters).

**Functions:**

- [**chunk**](#agrag-chunking-recursive-RecursiveChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-recursive-RecursiveChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-recursive-RecursiveChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-recursive-RecursiveChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-recursive-RecursiveChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-recursive-RecursiveChunker-spans) – Return the half-open character spans this strategy cuts text into.

##### `agrag.chunking.recursive.RecursiveChunker.chunk` \{#agrag-chunking-recursive-RecursiveChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.recursive.RecursiveChunker.chunk_size` \{#agrag-chunking-recursive-RecursiveChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

##### `agrag.chunking.recursive.RecursiveChunker.fingerprint` \{#agrag-chunking-recursive-RecursiveChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.recursive.RecursiveChunker.levels` \{#agrag-chunking-recursive-RecursiveChunker-levels}

```python
levels: tuple[SplitLevel, ...] | None = None
```

##### `agrag.chunking.recursive.RecursiveChunker.min_characters_per_chunk` \{#agrag-chunking-recursive-RecursiveChunker-min_characters_per_chunk}

```python
min_characters_per_chunk: int = Field(default=24, gt=0)
```

##### `agrag.chunking.recursive.RecursiveChunker.model_config` \{#agrag-chunking-recursive-RecursiveChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.recursive.RecursiveChunker.model_copy` \{#agrag-chunking-recursive-RecursiveChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.recursive.RecursiveChunker.model_post_init` \{#agrag-chunking-recursive-RecursiveChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

##### `agrag.chunking.recursive.RecursiveChunker.settings` \{#agrag-chunking-recursive-RecursiveChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.recursive.RecursiveChunker.spans` \{#agrag-chunking-recursive-RecursiveChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the half-open character spans this strategy cuts text into.

A cut inside a character that a tokenizer splits into several tokens makes
an empty piece. This method drops empty pieces, and no text is lost with them.

**Parameters:**

- **text** (<code>str</code>) – The text to cut.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The spans, in order, all non-empty.

##### `agrag.chunking.recursive.RecursiveChunker.strategy` \{#agrag-chunking-recursive-RecursiveChunker-strategy}

```python
strategy: str
```

The strategy name, `"recursive"`.

##### `agrag.chunking.recursive.RecursiveChunker.tokenizer` \{#agrag-chunking-recursive-RecursiveChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

#### `agrag.chunking.recursive.SplitLevel` \{#agrag-chunking-recursive-SplitLevel}

Bases: <code>BaseModel</code>

One level of recursive split rules.

**Attributes:**

- [**delimiters**](#agrag-chunking-recursive-SplitLevel-delimiters) (<code>tuple\[str, ...\] | None</code>) – The strings to split on at this level. `None` means none.
- [**whitespace**](#agrag-chunking-recursive-SplitLevel-whitespace) (<code>bool</code>) – Whether to split on whitespace at this level.
- [**include_delim**](#agrag-chunking-recursive-SplitLevel-include_delim) (<code>Literal['prev', 'next'] | None</code>) – Whether a delimiter stays with the previous piece, the next
  piece, or is dropped.

##### `agrag.chunking.recursive.SplitLevel.delimiters` \{#agrag-chunking-recursive-SplitLevel-delimiters}

```python
delimiters: tuple[str, ...] | None = None
```

##### `agrag.chunking.recursive.SplitLevel.include_delim` \{#agrag-chunking-recursive-SplitLevel-include_delim}

```python
include_delim: Literal['prev', 'next'] | None = 'prev'
```

##### `agrag.chunking.recursive.SplitLevel.model_config` \{#agrag-chunking-recursive-SplitLevel-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.recursive.SplitLevel.whitespace` \{#agrag-chunking-recursive-SplitLevel-whitespace}

```python
whitespace: bool = False
```

### `agrag.chunking.rules` \{#agrag-chunking-rules}

Chunking rules: which chunker a document gets, as data.

**Classes:**

- [**Chunking**](#agrag-chunking-rules-Chunking) – An ordered list of chunking rules and a fallback chunker.
- [**ChunkingRule**](#agrag-chunking-rules-ChunkingRule) – A match and the chunker for the documents it matches.
- [**RuleMatch**](#agrag-chunking-rules-RuleMatch) – The documents a rule applies to.

**Attributes:**

- [**DEFAULT_CHUNKING**](#agrag-chunking-rules-DEFAULT_CHUNKING) –

#### `agrag.chunking.rules.Chunking` \{#agrag-chunking-rules-Chunking}

Bases: <code>BaseModel</code>

An ordered list of chunking rules and a fallback chunker.

The first rule that matches a document picks its chunker. A document that no
rule matches gets `fallback`.

**Attributes:**

- [**rules**](#agrag-chunking-rules-Chunking-rules) (<code>tuple\[[ChunkingRule](#agrag-chunking-rules-ChunkingRule), ...\]</code>) – The rules, most specific first.
- [**fallback**](#agrag-chunking-rules-Chunking-fallback) (<code>SerializeAsAny\[[Chunker](#agrag-chunking-base-Chunker)\]</code>) – The chunker for documents that no rule matches.

**Functions:**

- [**fingerprint**](#agrag-chunking-rules-Chunking-fingerprint) – Return a hash of every rule match and every chunker setting.
- [**select**](#agrag-chunking-rules-Chunking-select) – Pick the chunker for a document.

##### `agrag.chunking.rules.Chunking.fallback` \{#agrag-chunking-rules-Chunking-fallback}

```python
fallback: SerializeAsAny[Chunker]
```

##### `agrag.chunking.rules.Chunking.fingerprint` \{#agrag-chunking-rules-Chunking-fingerprint}

```python
fingerprint() -> str
```

Return a hash of every rule match and every chunker setting.

##### `agrag.chunking.rules.Chunking.model_config` \{#agrag-chunking-rules-Chunking-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.rules.Chunking.rules` \{#agrag-chunking-rules-Chunking-rules}

```python
rules: tuple[ChunkingRule, ...] = ()
```

##### `agrag.chunking.rules.Chunking.select` \{#agrag-chunking-rules-Chunking-select}

```python
select(document:Document) -> tuple[int | None, Chunker]
```

Pick the chunker for a document.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to chunk.

**Returns:**

- <code>int | None</code> – The index of the first matching rule and its chunker, or `None` and
- <code>[Chunker](#agrag-chunking-base-Chunker)</code> – the fallback when no rule matches.

#### `agrag.chunking.rules.ChunkingRule` \{#agrag-chunking-rules-ChunkingRule}

Bases: <code>BaseModel</code>

A match and the chunker for the documents it matches.

**Attributes:**

- [**match**](#agrag-chunking-rules-ChunkingRule-match) (<code>[RuleMatch](#agrag-chunking-rules-RuleMatch)</code>) – The documents this rule applies to.
- [**chunker**](#agrag-chunking-rules-ChunkingRule-chunker) (<code>SerializeAsAny\[[Chunker](#agrag-chunking-base-Chunker)\]</code>) – The chunker those documents get.

##### `agrag.chunking.rules.ChunkingRule.chunker` \{#agrag-chunking-rules-ChunkingRule-chunker}

```python
chunker: SerializeAsAny[Chunker]
```

##### `agrag.chunking.rules.ChunkingRule.match` \{#agrag-chunking-rules-ChunkingRule-match}

```python
match: RuleMatch
```

##### `agrag.chunking.rules.ChunkingRule.model_config` \{#agrag-chunking-rules-ChunkingRule-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

#### `agrag.chunking.rules.DEFAULT_CHUNKING` \{#agrag-chunking-rules-DEFAULT_CHUNKING}

```python
DEFAULT_CHUNKING = Chunking(rules=(ChunkingRule(match=RuleMatch(loader_names=['docling']), chunker=DoclingChunker()),), fallback=RecursiveChunker(tokenizer='character', chunk_size=1024, min_characters_per_chunk=24))
```

#### `agrag.chunking.rules.RuleMatch` \{#agrag-chunking-rules-RuleMatch}

Bases: <code>BaseModel</code>

The documents a rule applies to.

Every key is optional and a key left as `None` matches any value. Keys combine
with AND. A value in a list key matches if it equals any item of the list.

**Attributes:**

- [**loader_names**](#agrag-chunking-rules-RuleMatch-loader_names) (<code>tuple\[str, ...\] | None</code>) – Match `Document.loader_name`.
- [**source_formats**](#agrag-chunking-rules-RuleMatch-source_formats) (<code>tuple\[[SourceFormat](common.md#agrag-common-data_models-document-SourceFormat), ...\] | None</code>) – Match `Document.source_format`.
- [**families**](#agrag-chunking-rules-RuleMatch-families) (<code>tuple\[[DocumentFamily](common.md#agrag-common-data_models-document-DocumentFamily), ...\] | None</code>) – Match `Document.family`.
- [**uri_glob**](#agrag-chunking-rules-RuleMatch-uri_glob) (<code>str | None</code>) – Match `Document.uri` against this `fnmatch` pattern. Case
  sensitive.

**Functions:**

- [**matches**](#agrag-chunking-rules-RuleMatch-matches) – Return whether every set key matches the document.

##### `agrag.chunking.rules.RuleMatch.families` \{#agrag-chunking-rules-RuleMatch-families}

```python
families: tuple[DocumentFamily, ...] | None = None
```

##### `agrag.chunking.rules.RuleMatch.loader_names` \{#agrag-chunking-rules-RuleMatch-loader_names}

```python
loader_names: tuple[str, ...] | None = None
```

##### `agrag.chunking.rules.RuleMatch.matches` \{#agrag-chunking-rules-RuleMatch-matches}

```python
matches(document:Document) -> bool
```

Return whether every set key matches the document.

##### `agrag.chunking.rules.RuleMatch.model_config` \{#agrag-chunking-rules-RuleMatch-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.rules.RuleMatch.source_formats` \{#agrag-chunking-rules-RuleMatch-source_formats}

```python
source_formats: tuple[SourceFormat, ...] | None = None
```

##### `agrag.chunking.rules.RuleMatch.uri_glob` \{#agrag-chunking-rules-RuleMatch-uri_glob}

```python
uri_glob: str | None = None
```

### `agrag.chunking.sentence` \{#agrag-chunking-sentence}

The sentence strategy: whole sentences packed up to a token budget.

**Classes:**

- [**SentenceChunker**](#agrag-chunking-sentence-SentenceChunker) – Packs whole sentences into chunks of at most `chunk_size` tokens.

#### `agrag.chunking.sentence.SentenceChunker` \{#agrag-chunking-sentence-SentenceChunker}

Bases: <code>[SpanChunker](#agrag-chunking-base-SpanChunker)</code>

Packs whole sentences into chunks of at most `chunk_size` tokens.

A single sentence longer than `chunk_size` stays whole, so a chunk can be
larger than the budget when the text has a very long sentence.

**Attributes:**

- [**chunk_size**](#agrag-chunking-sentence-SentenceChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**chunk_overlap**](#agrag-chunking-sentence-SentenceChunker-chunk_overlap) (<code>int</code>) – The overlap between neighbours, in tokens. Each chunk keeps
  its exact span in the document.
- [**min_sentences_per_chunk**](#agrag-chunking-sentence-SentenceChunker-min_sentences_per_chunk) (<code>int</code>) – The fewest sentences in a chunk.
- [**min_characters_per_sentence**](#agrag-chunking-sentence-SentenceChunker-min_characters_per_sentence) (<code>int</code>) – The shortest text that counts as a sentence.
- [**tokenizer**](#agrag-chunking-sentence-SentenceChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-sentence-SentenceChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-sentence-SentenceChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-sentence-SentenceChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-sentence-SentenceChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-sentence-SentenceChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-sentence-SentenceChunker-spans) – Return the half-open character spans this strategy cuts text into.

##### `agrag.chunking.sentence.SentenceChunker.chunk` \{#agrag-chunking-sentence-SentenceChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.sentence.SentenceChunker.chunk_overlap` \{#agrag-chunking-sentence-SentenceChunker-chunk_overlap}

```python
chunk_overlap: int = Field(default=0, ge=0)
```

##### `agrag.chunking.sentence.SentenceChunker.chunk_size` \{#agrag-chunking-sentence-SentenceChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

##### `agrag.chunking.sentence.SentenceChunker.fingerprint` \{#agrag-chunking-sentence-SentenceChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.sentence.SentenceChunker.min_characters_per_sentence` \{#agrag-chunking-sentence-SentenceChunker-min_characters_per_sentence}

```python
min_characters_per_sentence: int = Field(default=12, gt=0)
```

##### `agrag.chunking.sentence.SentenceChunker.min_sentences_per_chunk` \{#agrag-chunking-sentence-SentenceChunker-min_sentences_per_chunk}

```python
min_sentences_per_chunk: int = Field(default=1, gt=0)
```

##### `agrag.chunking.sentence.SentenceChunker.model_config` \{#agrag-chunking-sentence-SentenceChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.sentence.SentenceChunker.model_copy` \{#agrag-chunking-sentence-SentenceChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.sentence.SentenceChunker.model_post_init` \{#agrag-chunking-sentence-SentenceChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

##### `agrag.chunking.sentence.SentenceChunker.settings` \{#agrag-chunking-sentence-SentenceChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.sentence.SentenceChunker.spans` \{#agrag-chunking-sentence-SentenceChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the half-open character spans this strategy cuts text into.

A cut inside a character that a tokenizer splits into several tokens makes
an empty piece. This method drops empty pieces, and no text is lost with them.

**Parameters:**

- **text** (<code>str</code>) – The text to cut.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The spans, in order, all non-empty.

##### `agrag.chunking.sentence.SentenceChunker.strategy` \{#agrag-chunking-sentence-SentenceChunker-strategy}

```python
strategy: str
```

The strategy name, `"sentence"`.

##### `agrag.chunking.sentence.SentenceChunker.tokenizer` \{#agrag-chunking-sentence-SentenceChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.token` \{#agrag-chunking-token}

The token strategy: fixed-size windows of tokens, with optional overlap.

**Classes:**

- [**TokenChunker**](#agrag-chunking-token-TokenChunker) – Cuts the text into windows of `chunk_size` tokens.

#### `agrag.chunking.token.TokenChunker` \{#agrag-chunking-token-TokenChunker}

Bases: <code>[SpanChunker](#agrag-chunking-base-SpanChunker)</code>

Cuts the text into windows of `chunk_size` tokens.

Neighbouring chunks overlap when `chunk_overlap` is set, and each chunk keeps
its exact span in the document.

**Attributes:**

- [**chunk_size**](#agrag-chunking-token-TokenChunker-chunk_size) (<code>int</code>) – The window size, counted with `tokenizer`.
- [**chunk_overlap**](#agrag-chunking-token-TokenChunker-chunk_overlap) (<code>int | float</code>) – The overlap between neighbours. An int counts tokens. A float
  from 0 up to 1 is a share of `chunk_size`.
- [**tokenizer**](#agrag-chunking-token-TokenChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-token-TokenChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-token-TokenChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-token-TokenChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-token-TokenChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-token-TokenChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-token-TokenChunker-spans) – Return the half-open character spans this strategy cuts text into.

##### `agrag.chunking.token.TokenChunker.chunk` \{#agrag-chunking-token-TokenChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.token.TokenChunker.chunk_overlap` \{#agrag-chunking-token-TokenChunker-chunk_overlap}

```python
chunk_overlap: int | float = Field(default=0, ge=0)
```

##### `agrag.chunking.token.TokenChunker.chunk_size` \{#agrag-chunking-token-TokenChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

##### `agrag.chunking.token.TokenChunker.fingerprint` \{#agrag-chunking-token-TokenChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.token.TokenChunker.model_config` \{#agrag-chunking-token-TokenChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.token.TokenChunker.model_copy` \{#agrag-chunking-token-TokenChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.token.TokenChunker.model_post_init` \{#agrag-chunking-token-TokenChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

##### `agrag.chunking.token.TokenChunker.settings` \{#agrag-chunking-token-TokenChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.token.TokenChunker.spans` \{#agrag-chunking-token-TokenChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the half-open character spans this strategy cuts text into.

A cut inside a character that a tokenizer splits into several tokens makes
an empty piece. This method drops empty pieces, and no text is lost with them.

**Parameters:**

- **text** (<code>str</code>) – The text to cut.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The spans, in order, all non-empty.

##### `agrag.chunking.token.TokenChunker.strategy` \{#agrag-chunking-token-TokenChunker-strategy}

```python
strategy: str
```

The strategy name, `"token"`.

##### `agrag.chunking.token.TokenChunker.tokenizer` \{#agrag-chunking-token-TokenChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

### `agrag.chunking.turns` \{#agrag-chunking-turns}

The turn-window strategy: whole chat turns packed to a token budget.

**Classes:**

- [**TurnWindowChunker**](#agrag-chunking-turns-TurnWindowChunker) – Packs whole chat turns into windows of at most `chunk_size` tokens.

#### `agrag.chunking.turns.TurnWindowChunker` \{#agrag-chunking-turns-TurnWindowChunker}

Bases: <code>[Chunker](#agrag-chunking-base-Chunker)</code>

Packs whole chat turns into windows of at most `chunk_size` tokens.

The chunker reads `Document.turns`. A window holds one or more whole turns, and
a chunk boundary never falls inside a turn. Tokens are counted for each turn
alone, so the separators between turns are not part of the count. Text before
the first turn joins the first window, and text after a turn joins the window
that holds that turn.

A turn above the budget is split by `fallback`, and its chunks have the
chunker name `turn-window:<fallback strategy>`. A document without turns is
split by `fallback` as a whole and its chunks have the same name.

**Attributes:**

- [**chunk_size**](#agrag-chunking-turns-TurnWindowChunker-chunk_size) (<code>int</code>) – The most tokens in a window, counted with `tokenizer`.
- [**turn_overlap**](#agrag-chunking-turns-TurnWindowChunker-turn_overlap) (<code>int</code>) – The number of turns that a window repeats from the window
  before it. A window always moves on by at least one turn.
- [**tokenizer**](#agrag-chunking-turns-TurnWindowChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**fallback**](#agrag-chunking-turns-TurnWindowChunker-fallback) (<code>SerializeAsAny\[[SpanChunker](#agrag-chunking-base-SpanChunker)\]</code>) – The chunker for a turn above the budget and for a document without
  turns.

**Functions:**

- [**chunk**](#agrag-chunking-turns-TurnWindowChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-turns-TurnWindowChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-turns-TurnWindowChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-turns-TurnWindowChunker-model_post_init) – Load the tokenizer once, so a bad name fails at construction.
- [**settings**](#agrag-chunking-turns-TurnWindowChunker-settings) – Return the strategy name and every setting as JSON-safe data.

##### `agrag.chunking.turns.TurnWindowChunker.chunk` \{#agrag-chunking-turns-TurnWindowChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](common.md#agrag-common-data_models-document-Document)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](#agrag-chunking-base-ChunkingError)</code> – The strategy returned chunks that break the contract.

##### `agrag.chunking.turns.TurnWindowChunker.chunk_size` \{#agrag-chunking-turns-TurnWindowChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

##### `agrag.chunking.turns.TurnWindowChunker.fallback` \{#agrag-chunking-turns-TurnWindowChunker-fallback}

```python
fallback: SerializeAsAny[SpanChunker] = Field(default_factory=RecursiveChunker)
```

##### `agrag.chunking.turns.TurnWindowChunker.fingerprint` \{#agrag-chunking-turns-TurnWindowChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

##### `agrag.chunking.turns.TurnWindowChunker.model_config` \{#agrag-chunking-turns-TurnWindowChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.chunking.turns.TurnWindowChunker.model_copy` \{#agrag-chunking-turns-TurnWindowChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

##### `agrag.chunking.turns.TurnWindowChunker.model_post_init` \{#agrag-chunking-turns-TurnWindowChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Load the tokenizer once, so a bad name fails at construction.

##### `agrag.chunking.turns.TurnWindowChunker.settings` \{#agrag-chunking-turns-TurnWindowChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

##### `agrag.chunking.turns.TurnWindowChunker.strategy` \{#agrag-chunking-turns-TurnWindowChunker-strategy}

```python
strategy: str
```

The strategy name, `"turn-window"`.

##### `agrag.chunking.turns.TurnWindowChunker.tokenizer` \{#agrag-chunking-turns-TurnWindowChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

##### `agrag.chunking.turns.TurnWindowChunker.turn_overlap` \{#agrag-chunking-turns-TurnWindowChunker-turn_overlap}

```python
turn_overlap: int = Field(default=0, ge=0)
```
