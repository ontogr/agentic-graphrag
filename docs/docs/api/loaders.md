---
title: agrag.loaders
sidebar_position: 9
---

## `agrag.loaders` \{#agrag-loaders}

Document loaders: turn files, directories and raw text into Documents.

The docling loader needs the `docling` extra and lives in `agrag.loaders.docling`.

**Modules:**

- [**corpus**](#agrag-loaders-corpus) – The corpus loaders package.
- [**docling**](#agrag-loaders-docling) – The docling loader package.
- [**registry**](#agrag-loaders-registry) – The extension-to-loader registry.

**Classes:**

- [**DecodeError**](#agrag-loaders-DecodeError) – The source bytes do not decode to text.
- [**DocumentConversionError**](#agrag-loaders-DocumentConversionError) – A loader could not parse or convert a source's content.
- [**DocumentTooLargeError**](#agrag-loaders-DocumentTooLargeError) – A prose source is larger than the configured byte limit.
- [**ErrorPolicy**](#agrag-loaders-ErrorPolicy) – The action to take when one source in a batch fails.
- [**IngestResult**](#agrag-loaders-IngestResult) – The result of one ingest call.
- [**IngestionError**](#agrag-loaders-IngestionError) – The base class for every ingestion error.
- [**LoadStats**](#agrag-loaders-LoadStats) – Running tally of a corpus walk.
- [**LoaderRegistry**](#agrag-loaders-LoaderRegistry) – Maps a source extension to the loader that reads it.
- [**MalformedRecordError**](#agrag-loaders-MalformedRecordError) – One record in a record-family source does not parse.
- [**MissingExtraError**](#agrag-loaders-MissingExtraError) – A loader exists for this format, but its package extra is not installed.
- [**ReadOptions**](#agrag-loaders-ReadOptions) – Per-source reader configuration.
- [**UnsupportedFormatError**](#agrag-loaders-UnsupportedFormatError) – No registered loader can read this source's format.

### `agrag.loaders.DecodeError` \{#agrag-loaders-DecodeError}

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

The source bytes do not decode to text.

### `agrag.loaders.DocumentConversionError` \{#agrag-loaders-DocumentConversionError}

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

A loader could not parse or convert a source's content.

### `agrag.loaders.DocumentTooLargeError` \{#agrag-loaders-DocumentTooLargeError}

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

A prose source is larger than the configured byte limit.

### `agrag.loaders.ErrorPolicy` \{#agrag-loaders-ErrorPolicy}

Bases: <code>StrEnum</code>

The action to take when one source in a batch fails.

The policy applies to each source separately. `RAISE` is the default of
`Graph.add`.

**Attributes:**

- [**QUARANTINE**](#agrag-loaders-ErrorPolicy-QUARANTINE) – Set the failing source aside and record it in `quarantined_items`.
- [**RAISE**](#agrag-loaders-ErrorPolicy-RAISE) – Stop the whole run and raise the first error.
- [**SKIP**](#agrag-loaders-ErrorPolicy-SKIP) – Drop the failing source and count it in `skipped`.

#### `agrag.loaders.ErrorPolicy.QUARANTINE` \{#agrag-loaders-ErrorPolicy-QUARANTINE}

```python
QUARANTINE = 'quarantine'
```

Set the failing source aside and record it in `quarantined_items`.

#### `agrag.loaders.ErrorPolicy.RAISE` \{#agrag-loaders-ErrorPolicy-RAISE}

```python
RAISE = 'raise'
```

Stop the whole run and raise the first error.

#### `agrag.loaders.ErrorPolicy.SKIP` \{#agrag-loaders-ErrorPolicy-SKIP}

```python
SKIP = 'skip'
```

Drop the failing source and count it in `skipped`.

### `agrag.loaders.IngestResult` \{#agrag-loaders-IngestResult}

```python
IngestResult(documents:int = 0, sources:int = 0, skipped:int = 0, quarantined:int = 0, quarantined_items:list[tuple[str, str]] = list(), chunks:list[Chunk] = list()) -> None
```

The result of one ingest call.

**Attributes:**

- [**documents**](#agrag-loaders-IngestResult-documents) (<code>int</code>) – The number of documents the call produced.
- [**sources**](#agrag-loaders-IngestResult-sources) (<code>int</code>) – The number of sources the call read.
- [**skipped**](#agrag-loaders-IngestResult-skipped) (<code>int</code>) – The number of sources the call skipped.
- [**quarantined**](#agrag-loaders-IngestResult-quarantined) (<code>int</code>) – The number of sources the call moved to quarantine.
- [**quarantined_items**](#agrag-loaders-IngestResult-quarantined_items) (<code>list\[tuple\[str, str\]\]</code>) – The uri and reason for each quarantined source.
- [**chunks**](#agrag-loaders-IngestResult-chunks) (<code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – The chunks the call produced, in document then chunk order.

#### `agrag.loaders.IngestResult.chunks` \{#agrag-loaders-IngestResult-chunks}

```python
chunks: list[Chunk] = field(default_factory=list)
```

#### `agrag.loaders.IngestResult.documents` \{#agrag-loaders-IngestResult-documents}

```python
documents: int = 0
```

#### `agrag.loaders.IngestResult.quarantined` \{#agrag-loaders-IngestResult-quarantined}

```python
quarantined: int = 0
```

#### `agrag.loaders.IngestResult.quarantined_items` \{#agrag-loaders-IngestResult-quarantined_items}

```python
quarantined_items: list[tuple[str, str]] = field(default_factory=list)
```

#### `agrag.loaders.IngestResult.skipped` \{#agrag-loaders-IngestResult-skipped}

```python
skipped: int = 0
```

#### `agrag.loaders.IngestResult.sources` \{#agrag-loaders-IngestResult-sources}

```python
sources: int = 0
```

### `agrag.loaders.IngestionError` \{#agrag-loaders-IngestionError}

Bases: <code>Exception</code>

The base class for every ingestion error.

### `agrag.loaders.LoadStats` \{#agrag-loaders-LoadStats}

```python
LoadStats(documents:int = 0, sources:int = 0, bytes_read:int = 0, skipped:int = 0, quarantined:int = 0, quarantined_items:list[StageFailure] = list()) -> None
```

Running tally of a corpus walk.

**Attributes:**

- [**documents**](#agrag-loaders-LoadStats-documents) (<code>int</code>) – The number of documents read so far.
- [**sources**](#agrag-loaders-LoadStats-sources) (<code>int</code>) – The number of sources read so far.
- [**bytes_read**](#agrag-loaders-LoadStats-bytes_read) (<code>int</code>) – The number of bytes read so far.
- [**skipped**](#agrag-loaders-LoadStats-skipped) (<code>int</code>) – The number of sources skipped so far.
- [**quarantined**](#agrag-loaders-LoadStats-quarantined) (<code>int</code>) – The number of sources quarantined so far.
- [**quarantined_items**](#agrag-loaders-LoadStats-quarantined_items) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – One StageFailure per quarantined source so far.

#### `agrag.loaders.LoadStats.bytes_read` \{#agrag-loaders-LoadStats-bytes_read}

```python
bytes_read: int = 0
```

#### `agrag.loaders.LoadStats.documents` \{#agrag-loaders-LoadStats-documents}

```python
documents: int = 0
```

#### `agrag.loaders.LoadStats.quarantined` \{#agrag-loaders-LoadStats-quarantined}

```python
quarantined: int = 0
```

#### `agrag.loaders.LoadStats.quarantined_items` \{#agrag-loaders-LoadStats-quarantined_items}

```python
quarantined_items: list[StageFailure] = field(default_factory=list)
```

#### `agrag.loaders.LoadStats.skipped` \{#agrag-loaders-LoadStats-skipped}

```python
skipped: int = 0
```

#### `agrag.loaders.LoadStats.sources` \{#agrag-loaders-LoadStats-sources}

```python
sources: int = 0
```

### `agrag.loaders.LoaderRegistry` \{#agrag-loaders-LoaderRegistry}

```python
LoaderRegistry() -> None
```

Maps a source extension to the loader that reads it.

The registry picks a loader by file extension first. When more than one loader
claims
the same extension, the loader registered with `prefer=True` wins; when several
loaders
are preferred, the last preferred registration wins.

**Attributes:**

- **\_by_extension** (<code>dict\[str, list\[\_Entry\]\]</code>) – The registered loaders for each extension, in registration order.

**Functions:**

- [**for_source**](#agrag-loaders-LoaderRegistry-for_source) – Return the default loader for a source.
- [**register**](#agrag-loaders-LoaderRegistry-register) – Add a loader to the registry.

#### `agrag.loaders.LoaderRegistry.for_source` \{#agrag-loaders-LoaderRegistry-for_source}

```python
for_source(source:SourceRef) -> Loader
```

Return the default loader for a source.

**Parameters:**

- **source** (<code>[SourceRef](#agrag-loaders-corpus-types-SourceRef)</code>) – The source to find a loader for.

**Returns:**

- <code>[Loader](#agrag-loaders-corpus-base-Loader)</code> – The registered loader with the highest precedence for the source's
- <code>[Loader](#agrag-loaders-corpus-base-Loader)</code> – extension.

When the top-precedence loader needs a package extra that is not installed,
the first non-preferred loader for the extension whose extra (if any) is
installed is used instead, so an optional loader's absence falls back to the
core reader rather than always failing the source.

**Raises:**

- <code>[UnsupportedFormatError](#agrag-loaders-corpus-errors-UnsupportedFormatError)</code> – No loader claims the source's extension.
- <code>[MissingExtraError](#agrag-loaders-corpus-errors-MissingExtraError)</code> – A loader is mapped to the extension, but its package
  extra failed to import, and no fallback loader is available either.

#### `agrag.loaders.LoaderRegistry.register` \{#agrag-loaders-LoaderRegistry-register}

```python
register(loader:Loader, *, prefer:bool = False, extensions:set[str] | frozenset[str] | None = None) -> None
```

Add a loader to the registry.

Registering the same loader for the same extension more than once is a no-op, so
importing a package that registers loaders repeatedly stays safe.

**Parameters:**

- **loader** (<code>[Loader](#agrag-loaders-corpus-base-Loader)</code>) – The loader to register.
- **prefer** (<code>bool</code>) – Set this to True to make the loader the default for its extensions.
  Leave it False to register the loader only as an explicit, named option.
- **extensions** (<code>set\[str\] | frozenset\[str\] | None</code>) – Only register `loader` for these extensions. Defaults to every
  extension the loader advertises. A caller that wants different
  precedence per
  extension registers the same loader twice with different `extensions`
  sets.

### `agrag.loaders.MalformedRecordError` \{#agrag-loaders-MalformedRecordError}

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

One record in a record-family source does not parse.

### `agrag.loaders.MissingExtraError` \{#agrag-loaders-MissingExtraError}

```python
MissingExtraError(extension:str, extra:str) -> None
```

Bases: <code>[UnsupportedFormatError](#agrag-loaders-corpus-errors-UnsupportedFormatError)</code>

A loader exists for this format, but its package extra is not installed.

This class extends `UnsupportedFormatError` on purpose. An error policy can then
treat
a missing extra the same way it treats an unsupported format, instead of always
stopping
the whole batch.

**Attributes:**

- [**extension**](#agrag-loaders-MissingExtraError-extension) – The file extension that needs the extra.
- [**extra**](#agrag-loaders-MissingExtraError-extra) – The name of the package extra to install.

#### `agrag.loaders.MissingExtraError.extension` \{#agrag-loaders-MissingExtraError-extension}

```python
extension = extension
```

#### `agrag.loaders.MissingExtraError.extra` \{#agrag-loaders-MissingExtraError-extra}

```python
extra = extra
```

### `agrag.loaders.ReadOptions` \{#agrag-loaders-ReadOptions}

```python
ReadOptions(encoding:str | None = None, max_document_bytes:int = 32 * 1024 * 1024, store_text:bool = True, store_raw_record:bool = False, on_error:ErrorPolicy = ErrorPolicy.RAISE, text_column:str | None = None, id_column:str | None = None, title_column:str | None = None, json_mode:JsonMode = JsonMode.AUTO, csv_mode:CsvMode = CsvMode.ROWS, csv_delimiter:str | None = None, html_selector:str | None = None, normalization:Normalization = Normalization()) -> None
```

Per-source reader configuration.

Frozen so it is safe to share across worker processes.

**Attributes:**

- [**encoding**](#agrag-loaders-ReadOptions-encoding) (<code>str | None</code>) – The text encoding to use. `None` lets the decoder detect it.
- [**max_document_bytes**](#agrag-loaders-ReadOptions-max_document_bytes) (<code>int</code>) – The largest prose source the loader will read.
- [**store_text**](#agrag-loaders-ReadOptions-store_text) (<code>bool</code>) – When false, the document text is an empty string.
- [**store_raw_record**](#agrag-loaders-ReadOptions-store_raw_record) (<code>bool</code>) – When true, a record document keeps its raw row data.
- [**on_error**](#agrag-loaders-ReadOptions-on_error) (<code>[ErrorPolicy](#agrag-loaders-corpus-types-ErrorPolicy)</code>) – The error policy to apply inside the reader.
- [**text_column**](#agrag-loaders-ReadOptions-text_column) (<code>str | None</code>) – The column that holds document text. Required for record sources.
- [**id_column**](#agrag-loaders-ReadOptions-id_column) (<code>str | None</code>) – The column whose value becomes the document id.
- [**title_column**](#agrag-loaders-ReadOptions-title_column) (<code>str | None</code>) – The column whose value becomes the document title.
- [**json_mode**](#agrag-loaders-ReadOptions-json_mode) (<code>[JsonMode](#agrag-loaders-corpus-types-JsonMode)</code>) – The JSON reading mode.
- [**csv_mode**](#agrag-loaders-ReadOptions-csv_mode) (<code>[CsvMode](#agrag-loaders-corpus-types-CsvMode)</code>) – The CSV reading mode.
- [**csv_delimiter**](#agrag-loaders-ReadOptions-csv_delimiter) (<code>str | None</code>) – The column separator. `None` infers it from the extension.
- [**html_selector**](#agrag-loaders-ReadOptions-html_selector) (<code>str | None</code>) – The CSS selector for the main content of an HTML source.
- [**normalization**](#agrag-loaders-ReadOptions-normalization) (<code>[Normalization](common.md#agrag-common-data_models-normalization-Normalization)</code>) – How to normalize decoded text: byte-order mark, newline form
  and Unicode form. The default removes the mark, uses LF and applies NFKC.
  Chunk offsets index the normalized text.

#### `agrag.loaders.ReadOptions.csv_delimiter` \{#agrag-loaders-ReadOptions-csv_delimiter}

```python
csv_delimiter: str | None = None
```

#### `agrag.loaders.ReadOptions.csv_mode` \{#agrag-loaders-ReadOptions-csv_mode}

```python
csv_mode: CsvMode = CsvMode.ROWS
```

#### `agrag.loaders.ReadOptions.encoding` \{#agrag-loaders-ReadOptions-encoding}

```python
encoding: str | None = None
```

#### `agrag.loaders.ReadOptions.html_selector` \{#agrag-loaders-ReadOptions-html_selector}

```python
html_selector: str | None = None
```

#### `agrag.loaders.ReadOptions.id_column` \{#agrag-loaders-ReadOptions-id_column}

```python
id_column: str | None = None
```

#### `agrag.loaders.ReadOptions.json_mode` \{#agrag-loaders-ReadOptions-json_mode}

```python
json_mode: JsonMode = JsonMode.AUTO
```

#### `agrag.loaders.ReadOptions.max_document_bytes` \{#agrag-loaders-ReadOptions-max_document_bytes}

```python
max_document_bytes: int = 32 * 1024 * 1024
```

#### `agrag.loaders.ReadOptions.normalization` \{#agrag-loaders-ReadOptions-normalization}

```python
normalization: Normalization = field(default_factory=Normalization)
```

#### `agrag.loaders.ReadOptions.on_error` \{#agrag-loaders-ReadOptions-on_error}

```python
on_error: ErrorPolicy = ErrorPolicy.RAISE
```

#### `agrag.loaders.ReadOptions.store_raw_record` \{#agrag-loaders-ReadOptions-store_raw_record}

```python
store_raw_record: bool = False
```

#### `agrag.loaders.ReadOptions.store_text` \{#agrag-loaders-ReadOptions-store_text}

```python
store_text: bool = True
```

#### `agrag.loaders.ReadOptions.text_column` \{#agrag-loaders-ReadOptions-text_column}

```python
text_column: str | None = None
```

#### `agrag.loaders.ReadOptions.title_column` \{#agrag-loaders-ReadOptions-title_column}

```python
title_column: str | None = None
```

### `agrag.loaders.UnsupportedFormatError` \{#agrag-loaders-UnsupportedFormatError}

```python
UnsupportedFormatError(extension:str) -> None
```

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

No registered loader can read this source's format.

**Attributes:**

- [**extension**](#agrag-loaders-UnsupportedFormatError-extension) – The file extension that no loader claims.

#### `agrag.loaders.UnsupportedFormatError.extension` \{#agrag-loaders-UnsupportedFormatError-extension}

```python
extension = extension
```

### `agrag.loaders.corpus` \{#agrag-loaders-corpus}

The corpus loaders package.

Importing this package registers every core loader with the module-level `registry`
singleton. The docling extra registers itself on top of this when installed.

**Modules:**

- [**base**](#agrag-loaders-corpus-base) – The Loader interface: reads one source and yields Document objects.
- [**decode**](#agrag-loaders-corpus-decode) – The four-step decode pipeline for source bytes.
- [**errors**](#agrag-loaders-corpus-errors) – Errors that the ingestion layer raises.
- [**registry**](#agrag-loaders-corpus-registry) – The extension-to-loader registry.
- [**types**](#agrag-loaders-corpus-types) – Plumbing types for the corpus loaders.

#### `agrag.loaders.corpus.base` \{#agrag-loaders-corpus-base}

The Loader interface: reads one source and yields Document objects.

**Classes:**

- [**Loader**](#agrag-loaders-corpus-base-Loader) – Reads one source and yields Document objects.
- [**ProseLoader**](#agrag-loaders-corpus-base-ProseLoader) – A loader that makes one Document per source.
- [**RecordLoader**](#agrag-loaders-corpus-base-RecordLoader) – A loader that makes one Document per record in a source.

##### `agrag.loaders.corpus.base.Loader` \{#agrag-loaders-corpus-base-Loader}

Bases: <code>ABC</code>

Reads one source and yields Document objects.

A Loader keeps no state between calls, so a worker process can reuse one instance
across many sources.

**Attributes:**

- [**extensions**](#agrag-loaders-corpus-base-Loader-extensions) (<code>frozenset\[str\]</code>) – The file extensions this loader claims, each with a leading dot.
- [**mime_types**](#agrag-loaders-corpus-base-Loader-mime_types) (<code>frozenset\[str\]</code>) – The MIME types this loader claims. Empty when the loader relies on
  the extension alone.
- [**family**](#agrag-loaders-corpus-base-Loader-family) (<code>[DocumentFamily](common.md#agrag-common-data_models-document-DocumentFamily)</code>) – The document family this loader produces.
- [**extra**](#agrag-loaders-corpus-base-Loader-extra) (<code>str | None</code>) – The optional package extra required to use this loader. `None` for core
  loaders. The registry raises `MissingExtraError` when this extra is not
  installed.

**Functions:**

- [**load**](#agrag-loaders-corpus-base-Loader-load) – Yield documents read from one source.

###### `agrag.loaders.corpus.base.Loader.extensions` \{#agrag-loaders-corpus-base-Loader-extensions}

```python
extensions: frozenset[str]
```

###### `agrag.loaders.corpus.base.Loader.extra` \{#agrag-loaders-corpus-base-Loader-extra}

```python
extra: str | None = None
```

###### `agrag.loaders.corpus.base.Loader.family` \{#agrag-loaders-corpus-base-Loader-family}

```python
family: DocumentFamily
```

###### `agrag.loaders.corpus.base.Loader.load` \{#agrag-loaders-corpus-base-Loader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield documents read from one source.

**Parameters:**

- **source** (<code>[SourceRef](#agrag-loaders-corpus-types-SourceRef)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source, positioned at the start.
- **opts** (<code>[ReadOptions](#agrag-loaders-corpus-types-ReadOptions)</code>) – The read options for this call.
- **start_at** (<code>int</code>) – The record index to resume from. Prose loaders ignore this
  argument.

**Yields:**

- <code>[Document](common.md#agrag-common-data_models-document-Document)</code> – One Document per unit the source contains, in a fixed order.

###### `agrag.loaders.corpus.base.Loader.mime_types` \{#agrag-loaders-corpus-base-Loader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```

##### `agrag.loaders.corpus.base.ProseLoader` \{#agrag-loaders-corpus-base-ProseLoader}

Bases: <code>[Loader](#agrag-loaders-corpus-base-Loader)</code>

A loader that makes one Document per source.

Concrete readers reject a source larger than the configured byte limit when the
source's byte size is known upfront (`SourceRef.byte_size` is not `None`).

**Functions:**

- [**load**](#agrag-loaders-corpus-base-ProseLoader-load) – Yield documents read from one source.

**Attributes:**

- [**extensions**](#agrag-loaders-corpus-base-ProseLoader-extensions) (<code>frozenset\[str\]</code>) –
- [**extra**](#agrag-loaders-corpus-base-ProseLoader-extra) (<code>str | None</code>) –
- [**family**](#agrag-loaders-corpus-base-ProseLoader-family) –
- [**mime_types**](#agrag-loaders-corpus-base-ProseLoader-mime_types) (<code>frozenset\[str\]</code>) –

###### `agrag.loaders.corpus.base.ProseLoader.extensions` \{#agrag-loaders-corpus-base-ProseLoader-extensions}

```python
extensions: frozenset[str]
```

###### `agrag.loaders.corpus.base.ProseLoader.extra` \{#agrag-loaders-corpus-base-ProseLoader-extra}

```python
extra: str | None = None
```

###### `agrag.loaders.corpus.base.ProseLoader.family` \{#agrag-loaders-corpus-base-ProseLoader-family}

```python
family = DocumentFamily.PROSE
```

###### `agrag.loaders.corpus.base.ProseLoader.load` \{#agrag-loaders-corpus-base-ProseLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield documents read from one source.

**Parameters:**

- **source** (<code>[SourceRef](#agrag-loaders-corpus-types-SourceRef)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source, positioned at the start.
- **opts** (<code>[ReadOptions](#agrag-loaders-corpus-types-ReadOptions)</code>) – The read options for this call.
- **start_at** (<code>int</code>) – The record index to resume from. Prose loaders ignore this
  argument.

**Yields:**

- <code>[Document](common.md#agrag-common-data_models-document-Document)</code> – One Document per unit the source contains, in a fixed order.

###### `agrag.loaders.corpus.base.ProseLoader.mime_types` \{#agrag-loaders-corpus-base-ProseLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```

##### `agrag.loaders.corpus.base.RecordLoader` \{#agrag-loaders-corpus-base-RecordLoader}

Bases: <code>[Loader](#agrag-loaders-corpus-base-Loader)</code>

A loader that makes one Document per record in a source.

Concrete readers read and decode the whole source into memory up front, up
to `opts.max_document_bytes`; that byte limit is what bounds memory use,
not incremental reads from disk. Whether records are parsed incrementally
from there is format-dependent: the CSV and JSONL readers parse and yield
one record at a time, so a malformed record later in the source surfaces
only after earlier records have already been yielded. The JSON reader
parses the whole source up front, so a malformed source fails before any
record is yielded.

**Functions:**

- [**load**](#agrag-loaders-corpus-base-RecordLoader-load) – Yield documents read from one source.

**Attributes:**

- [**extensions**](#agrag-loaders-corpus-base-RecordLoader-extensions) (<code>frozenset\[str\]</code>) –
- [**extra**](#agrag-loaders-corpus-base-RecordLoader-extra) (<code>str | None</code>) –
- [**family**](#agrag-loaders-corpus-base-RecordLoader-family) –
- [**mime_types**](#agrag-loaders-corpus-base-RecordLoader-mime_types) (<code>frozenset\[str\]</code>) –

###### `agrag.loaders.corpus.base.RecordLoader.extensions` \{#agrag-loaders-corpus-base-RecordLoader-extensions}

```python
extensions: frozenset[str]
```

###### `agrag.loaders.corpus.base.RecordLoader.extra` \{#agrag-loaders-corpus-base-RecordLoader-extra}

```python
extra: str | None = None
```

###### `agrag.loaders.corpus.base.RecordLoader.family` \{#agrag-loaders-corpus-base-RecordLoader-family}

```python
family = DocumentFamily.RECORD
```

###### `agrag.loaders.corpus.base.RecordLoader.load` \{#agrag-loaders-corpus-base-RecordLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield documents read from one source.

**Parameters:**

- **source** (<code>[SourceRef](#agrag-loaders-corpus-types-SourceRef)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source, positioned at the start.
- **opts** (<code>[ReadOptions](#agrag-loaders-corpus-types-ReadOptions)</code>) – The read options for this call.
- **start_at** (<code>int</code>) – The record index to resume from. Prose loaders ignore this
  argument.

**Yields:**

- <code>[Document](common.md#agrag-common-data_models-document-Document)</code> – One Document per unit the source contains, in a fixed order.

###### `agrag.loaders.corpus.base.RecordLoader.mime_types` \{#agrag-loaders-corpus-base-RecordLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```

#### `agrag.loaders.corpus.decode` \{#agrag-loaders-corpus-decode}

The four-step decode pipeline for source bytes.

Every text loader shares this pipeline. It runs, in order: encoding detection via
charset-normalizer, byte-order-mark handling, newline normalization, and Unicode
normalization. `ReadOptions.normalization` sets the last three steps. It raises
`DecodeError` on failure rather than silently emitting mojibake.

**Functions:**

- [**decode_text**](#agrag-loaders-corpus-decode-decode_text) – Decode raw source bytes into normalized text.

##### `agrag.loaders.corpus.decode.decode_text` \{#agrag-loaders-corpus-decode-decode_text}

```python
decode_text(raw:bytes, opts:ReadOptions) -> DecodedText
```

Decode raw source bytes into normalized text.

This function detects the encoding, applies `opts.normalization` and hashes the
result. It raises `DecodeError` instead of returning garbled text.

**Parameters:**

- **raw** (<code>bytes</code>) – The raw source bytes.
- **opts** (<code>[ReadOptions](#agrag-loaders-corpus-types-ReadOptions)</code>) – The read options. `opts.encoding` forces a specific codec when set.

**Returns:**

- <code>[DecodedText](#agrag-loaders-corpus-types-DecodedText)</code> – The decoded text with its encoding and hash.

**Raises:**

- <code>[DecodeError](#agrag-loaders-corpus-errors-DecodeError)</code> – The bytes do not decode under the forced encoding, or detection
  fails and the latin-1 fallback is unavailable.

#### `agrag.loaders.corpus.errors` \{#agrag-loaders-corpus-errors}

Errors that the ingestion layer raises.

**Classes:**

- [**DecodeError**](#agrag-loaders-corpus-errors-DecodeError) – The source bytes do not decode to text.
- [**DocumentConversionError**](#agrag-loaders-corpus-errors-DocumentConversionError) – A loader could not parse or convert a source's content.
- [**DocumentTooLargeError**](#agrag-loaders-corpus-errors-DocumentTooLargeError) – A prose source is larger than the configured byte limit.
- [**IngestionError**](#agrag-loaders-corpus-errors-IngestionError) – The base class for every ingestion error.
- [**MalformedRecordError**](#agrag-loaders-corpus-errors-MalformedRecordError) – One record in a record-family source does not parse.
- [**MissingExtraError**](#agrag-loaders-corpus-errors-MissingExtraError) – A loader exists for this format, but its package extra is not installed.
- [**UnsupportedFormatError**](#agrag-loaders-corpus-errors-UnsupportedFormatError) – No registered loader can read this source's format.

##### `agrag.loaders.corpus.errors.DecodeError` \{#agrag-loaders-corpus-errors-DecodeError}

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

The source bytes do not decode to text.

##### `agrag.loaders.corpus.errors.DocumentConversionError` \{#agrag-loaders-corpus-errors-DocumentConversionError}

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

A loader could not parse or convert a source's content.

##### `agrag.loaders.corpus.errors.DocumentTooLargeError` \{#agrag-loaders-corpus-errors-DocumentTooLargeError}

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

A prose source is larger than the configured byte limit.

##### `agrag.loaders.corpus.errors.IngestionError` \{#agrag-loaders-corpus-errors-IngestionError}

Bases: <code>Exception</code>

The base class for every ingestion error.

##### `agrag.loaders.corpus.errors.MalformedRecordError` \{#agrag-loaders-corpus-errors-MalformedRecordError}

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

One record in a record-family source does not parse.

##### `agrag.loaders.corpus.errors.MissingExtraError` \{#agrag-loaders-corpus-errors-MissingExtraError}

```python
MissingExtraError(extension:str, extra:str) -> None
```

Bases: <code>[UnsupportedFormatError](#agrag-loaders-corpus-errors-UnsupportedFormatError)</code>

A loader exists for this format, but its package extra is not installed.

This class extends `UnsupportedFormatError` on purpose. An error policy can then
treat
a missing extra the same way it treats an unsupported format, instead of always
stopping
the whole batch.

**Attributes:**

- [**extension**](#agrag-loaders-corpus-errors-MissingExtraError-extension) – The file extension that needs the extra.
- [**extra**](#agrag-loaders-corpus-errors-MissingExtraError-extra) – The name of the package extra to install.

###### `agrag.loaders.corpus.errors.MissingExtraError.extension` \{#agrag-loaders-corpus-errors-MissingExtraError-extension}

```python
extension = extension
```

###### `agrag.loaders.corpus.errors.MissingExtraError.extra` \{#agrag-loaders-corpus-errors-MissingExtraError-extra}

```python
extra = extra
```

##### `agrag.loaders.corpus.errors.UnsupportedFormatError` \{#agrag-loaders-corpus-errors-UnsupportedFormatError}

```python
UnsupportedFormatError(extension:str) -> None
```

Bases: <code>[IngestionError](#agrag-loaders-corpus-errors-IngestionError)</code>

No registered loader can read this source's format.

**Attributes:**

- [**extension**](#agrag-loaders-corpus-errors-UnsupportedFormatError-extension) – The file extension that no loader claims.

###### `agrag.loaders.corpus.errors.UnsupportedFormatError.extension` \{#agrag-loaders-corpus-errors-UnsupportedFormatError-extension}

```python
extension = extension
```

#### `agrag.loaders.corpus.registry` \{#agrag-loaders-corpus-registry}

The extension-to-loader registry.

**Classes:**

- [**LoaderRegistry**](#agrag-loaders-corpus-registry-LoaderRegistry) – Maps a source extension to the loader that reads it.

##### `agrag.loaders.corpus.registry.LoaderRegistry` \{#agrag-loaders-corpus-registry-LoaderRegistry}

```python
LoaderRegistry() -> None
```

Maps a source extension to the loader that reads it.

The registry picks a loader by file extension first. When more than one loader
claims
the same extension, the loader registered with `prefer=True` wins; when several
loaders
are preferred, the last preferred registration wins.

**Attributes:**

- **\_by_extension** (<code>dict\[str, list\[\_Entry\]\]</code>) – The registered loaders for each extension, in registration order.

**Functions:**

- [**for_source**](#agrag-loaders-corpus-registry-LoaderRegistry-for_source) – Return the default loader for a source.
- [**register**](#agrag-loaders-corpus-registry-LoaderRegistry-register) – Add a loader to the registry.

###### `agrag.loaders.corpus.registry.LoaderRegistry.for_source` \{#agrag-loaders-corpus-registry-LoaderRegistry-for_source}

```python
for_source(source:SourceRef) -> Loader
```

Return the default loader for a source.

**Parameters:**

- **source** (<code>[SourceRef](#agrag-loaders-corpus-types-SourceRef)</code>) – The source to find a loader for.

**Returns:**

- <code>[Loader](#agrag-loaders-corpus-base-Loader)</code> – The registered loader with the highest precedence for the source's
- <code>[Loader](#agrag-loaders-corpus-base-Loader)</code> – extension.

When the top-precedence loader needs a package extra that is not installed,
the first non-preferred loader for the extension whose extra (if any) is
installed is used instead, so an optional loader's absence falls back to the
core reader rather than always failing the source.

**Raises:**

- <code>[UnsupportedFormatError](#agrag-loaders-corpus-errors-UnsupportedFormatError)</code> – No loader claims the source's extension.
- <code>[MissingExtraError](#agrag-loaders-corpus-errors-MissingExtraError)</code> – A loader is mapped to the extension, but its package
  extra failed to import, and no fallback loader is available either.

###### `agrag.loaders.corpus.registry.LoaderRegistry.register` \{#agrag-loaders-corpus-registry-LoaderRegistry-register}

```python
register(loader:Loader, *, prefer:bool = False, extensions:set[str] | frozenset[str] | None = None) -> None
```

Add a loader to the registry.

Registering the same loader for the same extension more than once is a no-op, so
importing a package that registers loaders repeatedly stays safe.

**Parameters:**

- **loader** (<code>[Loader](#agrag-loaders-corpus-base-Loader)</code>) – The loader to register.
- **prefer** (<code>bool</code>) – Set this to True to make the loader the default for its extensions.
  Leave it False to register the loader only as an explicit, named option.
- **extensions** (<code>set\[str\] | frozenset\[str\] | None</code>) – Only register `loader` for these extensions. Defaults to every
  extension the loader advertises. A caller that wants different
  precedence per
  extension registers the same loader twice with different `extensions`
  sets.

#### `agrag.loaders.corpus.types` \{#agrag-loaders-corpus-types}

Plumbing types for the corpus loaders.

These types support the loader, decode, and walk machinery. They are feature-local to
`agrag.loaders.corpus` and are not domain models.

**Classes:**

- [**CsvMode**](#agrag-loaders-corpus-types-CsvMode) – How to read a CSV or TSV source.
- [**DecodedText**](#agrag-loaders-corpus-types-DecodedText) – Output of the four-step decode pipeline.
- [**ErrorPolicy**](#agrag-loaders-corpus-types-ErrorPolicy) – The action to take when one source in a batch fails.
- [**IngestResult**](#agrag-loaders-corpus-types-IngestResult) – The result of one ingest call.
- [**JsonMode**](#agrag-loaders-corpus-types-JsonMode) – How to read a JSON source.
- [**LoadStats**](#agrag-loaders-corpus-types-LoadStats) – Running tally of a corpus walk.
- [**LoaderCursor**](#agrag-loaders-corpus-types-LoaderCursor) – Resume point for a corpus walk.
- [**ReadOptions**](#agrag-loaders-corpus-types-ReadOptions) – Per-source reader configuration.
- [**SourceRef**](#agrag-loaders-corpus-types-SourceRef) – A locatable input, before any bytes are read.

##### `agrag.loaders.corpus.types.CsvMode` \{#agrag-loaders-corpus-types-CsvMode}

Bases: <code>StrEnum</code>

How to read a CSV or TSV source.

ROWS: Read one document per row.
TABLE: Read the whole table as one document.

**Attributes:**

- [**ROWS**](#agrag-loaders-corpus-types-CsvMode-ROWS) –
- [**TABLE**](#agrag-loaders-corpus-types-CsvMode-TABLE) –

###### `agrag.loaders.corpus.types.CsvMode.ROWS` \{#agrag-loaders-corpus-types-CsvMode-ROWS}

```python
ROWS = 'rows'
```

###### `agrag.loaders.corpus.types.CsvMode.TABLE` \{#agrag-loaders-corpus-types-CsvMode-TABLE}

```python
TABLE = 'table'
```

##### `agrag.loaders.corpus.types.DecodedText` \{#agrag-loaders-corpus-types-DecodedText}

```python
DecodedText(text:str, encoding:str, had_bom:bool, content_hash:str, char_count:int, line_count:int) -> None
```

Output of the four-step decode pipeline.

**Attributes:**

- [**text**](#agrag-loaders-corpus-types-DecodedText-text) (<code>str</code>) – The decoded text, normalized as `ReadOptions.normalization` says.
- [**encoding**](#agrag-loaders-corpus-types-DecodedText-encoding) (<code>str</code>) – The encoding used to decode the bytes.
- [**had_bom**](#agrag-loaders-corpus-types-DecodedText-had_bom) (<code>bool</code>) – Whether the source started with a byte-order mark.
- [**content_hash**](#agrag-loaders-corpus-types-DecodedText-content_hash) (<code>str</code>) – The sha256 hash of the normalized text.
- [**char_count**](#agrag-loaders-corpus-types-DecodedText-char_count) (<code>int</code>) – The number of characters in `text`.
- [**line_count**](#agrag-loaders-corpus-types-DecodedText-line_count) (<code>int</code>) – The number of lines in `text`.

###### `agrag.loaders.corpus.types.DecodedText.char_count` \{#agrag-loaders-corpus-types-DecodedText-char_count}

```python
char_count: int
```

###### `agrag.loaders.corpus.types.DecodedText.content_hash` \{#agrag-loaders-corpus-types-DecodedText-content_hash}

```python
content_hash: str
```

###### `agrag.loaders.corpus.types.DecodedText.encoding` \{#agrag-loaders-corpus-types-DecodedText-encoding}

```python
encoding: str
```

###### `agrag.loaders.corpus.types.DecodedText.had_bom` \{#agrag-loaders-corpus-types-DecodedText-had_bom}

```python
had_bom: bool
```

###### `agrag.loaders.corpus.types.DecodedText.line_count` \{#agrag-loaders-corpus-types-DecodedText-line_count}

```python
line_count: int
```

###### `agrag.loaders.corpus.types.DecodedText.text` \{#agrag-loaders-corpus-types-DecodedText-text}

```python
text: str
```

##### `agrag.loaders.corpus.types.ErrorPolicy` \{#agrag-loaders-corpus-types-ErrorPolicy}

Bases: <code>StrEnum</code>

The action to take when one source in a batch fails.

The policy applies to each source separately. `RAISE` is the default of
`Graph.add`.

**Attributes:**

- [**QUARANTINE**](#agrag-loaders-corpus-types-ErrorPolicy-QUARANTINE) – Set the failing source aside and record it in `quarantined_items`.
- [**RAISE**](#agrag-loaders-corpus-types-ErrorPolicy-RAISE) – Stop the whole run and raise the first error.
- [**SKIP**](#agrag-loaders-corpus-types-ErrorPolicy-SKIP) – Drop the failing source and count it in `skipped`.

###### `agrag.loaders.corpus.types.ErrorPolicy.QUARANTINE` \{#agrag-loaders-corpus-types-ErrorPolicy-QUARANTINE}

```python
QUARANTINE = 'quarantine'
```

Set the failing source aside and record it in `quarantined_items`.

###### `agrag.loaders.corpus.types.ErrorPolicy.RAISE` \{#agrag-loaders-corpus-types-ErrorPolicy-RAISE}

```python
RAISE = 'raise'
```

Stop the whole run and raise the first error.

###### `agrag.loaders.corpus.types.ErrorPolicy.SKIP` \{#agrag-loaders-corpus-types-ErrorPolicy-SKIP}

```python
SKIP = 'skip'
```

Drop the failing source and count it in `skipped`.

##### `agrag.loaders.corpus.types.IngestResult` \{#agrag-loaders-corpus-types-IngestResult}

```python
IngestResult(documents:int = 0, sources:int = 0, skipped:int = 0, quarantined:int = 0, quarantined_items:list[tuple[str, str]] = list(), chunks:list[Chunk] = list()) -> None
```

The result of one ingest call.

**Attributes:**

- [**documents**](#agrag-loaders-corpus-types-IngestResult-documents) (<code>int</code>) – The number of documents the call produced.
- [**sources**](#agrag-loaders-corpus-types-IngestResult-sources) (<code>int</code>) – The number of sources the call read.
- [**skipped**](#agrag-loaders-corpus-types-IngestResult-skipped) (<code>int</code>) – The number of sources the call skipped.
- [**quarantined**](#agrag-loaders-corpus-types-IngestResult-quarantined) (<code>int</code>) – The number of sources the call moved to quarantine.
- [**quarantined_items**](#agrag-loaders-corpus-types-IngestResult-quarantined_items) (<code>list\[tuple\[str, str\]\]</code>) – The uri and reason for each quarantined source.
- [**chunks**](#agrag-loaders-corpus-types-IngestResult-chunks) (<code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – The chunks the call produced, in document then chunk order.

###### `agrag.loaders.corpus.types.IngestResult.chunks` \{#agrag-loaders-corpus-types-IngestResult-chunks}

```python
chunks: list[Chunk] = field(default_factory=list)
```

###### `agrag.loaders.corpus.types.IngestResult.documents` \{#agrag-loaders-corpus-types-IngestResult-documents}

```python
documents: int = 0
```

###### `agrag.loaders.corpus.types.IngestResult.quarantined` \{#agrag-loaders-corpus-types-IngestResult-quarantined}

```python
quarantined: int = 0
```

###### `agrag.loaders.corpus.types.IngestResult.quarantined_items` \{#agrag-loaders-corpus-types-IngestResult-quarantined_items}

```python
quarantined_items: list[tuple[str, str]] = field(default_factory=list)
```

###### `agrag.loaders.corpus.types.IngestResult.skipped` \{#agrag-loaders-corpus-types-IngestResult-skipped}

```python
skipped: int = 0
```

###### `agrag.loaders.corpus.types.IngestResult.sources` \{#agrag-loaders-corpus-types-IngestResult-sources}

```python
sources: int = 0
```

##### `agrag.loaders.corpus.types.JsonMode` \{#agrag-loaders-corpus-types-JsonMode}

Bases: <code>StrEnum</code>

How to read a JSON source.

AUTO: Read an array as records and an object as one document.
RECORDS: Read a top-level array as one document per element.
DOCUMENT: Read a top-level array as one document that holds the whole array.

**Attributes:**

- [**AUTO**](#agrag-loaders-corpus-types-JsonMode-AUTO) –
- [**DOCUMENT**](#agrag-loaders-corpus-types-JsonMode-DOCUMENT) –
- [**RECORDS**](#agrag-loaders-corpus-types-JsonMode-RECORDS) –

###### `agrag.loaders.corpus.types.JsonMode.AUTO` \{#agrag-loaders-corpus-types-JsonMode-AUTO}

```python
AUTO = 'auto'
```

###### `agrag.loaders.corpus.types.JsonMode.DOCUMENT` \{#agrag-loaders-corpus-types-JsonMode-DOCUMENT}

```python
DOCUMENT = 'document'
```

###### `agrag.loaders.corpus.types.JsonMode.RECORDS` \{#agrag-loaders-corpus-types-JsonMode-RECORDS}

```python
RECORDS = 'records'
```

##### `agrag.loaders.corpus.types.LoadStats` \{#agrag-loaders-corpus-types-LoadStats}

```python
LoadStats(documents:int = 0, sources:int = 0, bytes_read:int = 0, skipped:int = 0, quarantined:int = 0, quarantined_items:list[StageFailure] = list()) -> None
```

Running tally of a corpus walk.

**Attributes:**

- [**documents**](#agrag-loaders-corpus-types-LoadStats-documents) (<code>int</code>) – The number of documents read so far.
- [**sources**](#agrag-loaders-corpus-types-LoadStats-sources) (<code>int</code>) – The number of sources read so far.
- [**bytes_read**](#agrag-loaders-corpus-types-LoadStats-bytes_read) (<code>int</code>) – The number of bytes read so far.
- [**skipped**](#agrag-loaders-corpus-types-LoadStats-skipped) (<code>int</code>) – The number of sources skipped so far.
- [**quarantined**](#agrag-loaders-corpus-types-LoadStats-quarantined) (<code>int</code>) – The number of sources quarantined so far.
- [**quarantined_items**](#agrag-loaders-corpus-types-LoadStats-quarantined_items) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – One StageFailure per quarantined source so far.

###### `agrag.loaders.corpus.types.LoadStats.bytes_read` \{#agrag-loaders-corpus-types-LoadStats-bytes_read}

```python
bytes_read: int = 0
```

###### `agrag.loaders.corpus.types.LoadStats.documents` \{#agrag-loaders-corpus-types-LoadStats-documents}

```python
documents: int = 0
```

###### `agrag.loaders.corpus.types.LoadStats.quarantined` \{#agrag-loaders-corpus-types-LoadStats-quarantined}

```python
quarantined: int = 0
```

###### `agrag.loaders.corpus.types.LoadStats.quarantined_items` \{#agrag-loaders-corpus-types-LoadStats-quarantined_items}

```python
quarantined_items: list[StageFailure] = field(default_factory=list)
```

###### `agrag.loaders.corpus.types.LoadStats.skipped` \{#agrag-loaders-corpus-types-LoadStats-skipped}

```python
skipped: int = 0
```

###### `agrag.loaders.corpus.types.LoadStats.sources` \{#agrag-loaders-corpus-types-LoadStats-sources}

```python
sources: int = 0
```

##### `agrag.loaders.corpus.types.LoaderCursor` \{#agrag-loaders-corpus-types-LoaderCursor}

```python
LoaderCursor(uri:str | None = None, record_index:int | None = None) -> None
```

Resume point for a corpus walk.

Ordering is deterministic, so a cursor is replayable.

**Attributes:**

- [**uri**](#agrag-loaders-corpus-types-LoaderCursor-uri) (<code>str | None</code>) – The source to resume after. `None` means start at the beginning.
- [**record_index**](#agrag-loaders-corpus-types-LoaderCursor-record_index) (<code>int | None</code>) – The record to resume after within the source. `None` means the
  start.

###### `agrag.loaders.corpus.types.LoaderCursor.record_index` \{#agrag-loaders-corpus-types-LoaderCursor-record_index}

```python
record_index: int | None = None
```

###### `agrag.loaders.corpus.types.LoaderCursor.uri` \{#agrag-loaders-corpus-types-LoaderCursor-uri}

```python
uri: str | None = None
```

##### `agrag.loaders.corpus.types.ReadOptions` \{#agrag-loaders-corpus-types-ReadOptions}

```python
ReadOptions(encoding:str | None = None, max_document_bytes:int = 32 * 1024 * 1024, store_text:bool = True, store_raw_record:bool = False, on_error:ErrorPolicy = ErrorPolicy.RAISE, text_column:str | None = None, id_column:str | None = None, title_column:str | None = None, json_mode:JsonMode = JsonMode.AUTO, csv_mode:CsvMode = CsvMode.ROWS, csv_delimiter:str | None = None, html_selector:str | None = None, normalization:Normalization = Normalization()) -> None
```

Per-source reader configuration.

Frozen so it is safe to share across worker processes.

**Attributes:**

- [**encoding**](#agrag-loaders-corpus-types-ReadOptions-encoding) (<code>str | None</code>) – The text encoding to use. `None` lets the decoder detect it.
- [**max_document_bytes**](#agrag-loaders-corpus-types-ReadOptions-max_document_bytes) (<code>int</code>) – The largest prose source the loader will read.
- [**store_text**](#agrag-loaders-corpus-types-ReadOptions-store_text) (<code>bool</code>) – When false, the document text is an empty string.
- [**store_raw_record**](#agrag-loaders-corpus-types-ReadOptions-store_raw_record) (<code>bool</code>) – When true, a record document keeps its raw row data.
- [**on_error**](#agrag-loaders-corpus-types-ReadOptions-on_error) (<code>[ErrorPolicy](#agrag-loaders-corpus-types-ErrorPolicy)</code>) – The error policy to apply inside the reader.
- [**text_column**](#agrag-loaders-corpus-types-ReadOptions-text_column) (<code>str | None</code>) – The column that holds document text. Required for record sources.
- [**id_column**](#agrag-loaders-corpus-types-ReadOptions-id_column) (<code>str | None</code>) – The column whose value becomes the document id.
- [**title_column**](#agrag-loaders-corpus-types-ReadOptions-title_column) (<code>str | None</code>) – The column whose value becomes the document title.
- [**json_mode**](#agrag-loaders-corpus-types-ReadOptions-json_mode) (<code>[JsonMode](#agrag-loaders-corpus-types-JsonMode)</code>) – The JSON reading mode.
- [**csv_mode**](#agrag-loaders-corpus-types-ReadOptions-csv_mode) (<code>[CsvMode](#agrag-loaders-corpus-types-CsvMode)</code>) – The CSV reading mode.
- [**csv_delimiter**](#agrag-loaders-corpus-types-ReadOptions-csv_delimiter) (<code>str | None</code>) – The column separator. `None` infers it from the extension.
- [**html_selector**](#agrag-loaders-corpus-types-ReadOptions-html_selector) (<code>str | None</code>) – The CSS selector for the main content of an HTML source.
- [**normalization**](#agrag-loaders-corpus-types-ReadOptions-normalization) (<code>[Normalization](common.md#agrag-common-data_models-normalization-Normalization)</code>) – How to normalize decoded text: byte-order mark, newline form
  and Unicode form. The default removes the mark, uses LF and applies NFKC.
  Chunk offsets index the normalized text.

###### `agrag.loaders.corpus.types.ReadOptions.csv_delimiter` \{#agrag-loaders-corpus-types-ReadOptions-csv_delimiter}

```python
csv_delimiter: str | None = None
```

###### `agrag.loaders.corpus.types.ReadOptions.csv_mode` \{#agrag-loaders-corpus-types-ReadOptions-csv_mode}

```python
csv_mode: CsvMode = CsvMode.ROWS
```

###### `agrag.loaders.corpus.types.ReadOptions.encoding` \{#agrag-loaders-corpus-types-ReadOptions-encoding}

```python
encoding: str | None = None
```

###### `agrag.loaders.corpus.types.ReadOptions.html_selector` \{#agrag-loaders-corpus-types-ReadOptions-html_selector}

```python
html_selector: str | None = None
```

###### `agrag.loaders.corpus.types.ReadOptions.id_column` \{#agrag-loaders-corpus-types-ReadOptions-id_column}

```python
id_column: str | None = None
```

###### `agrag.loaders.corpus.types.ReadOptions.json_mode` \{#agrag-loaders-corpus-types-ReadOptions-json_mode}

```python
json_mode: JsonMode = JsonMode.AUTO
```

###### `agrag.loaders.corpus.types.ReadOptions.max_document_bytes` \{#agrag-loaders-corpus-types-ReadOptions-max_document_bytes}

```python
max_document_bytes: int = 32 * 1024 * 1024
```

###### `agrag.loaders.corpus.types.ReadOptions.normalization` \{#agrag-loaders-corpus-types-ReadOptions-normalization}

```python
normalization: Normalization = field(default_factory=Normalization)
```

###### `agrag.loaders.corpus.types.ReadOptions.on_error` \{#agrag-loaders-corpus-types-ReadOptions-on_error}

```python
on_error: ErrorPolicy = ErrorPolicy.RAISE
```

###### `agrag.loaders.corpus.types.ReadOptions.store_raw_record` \{#agrag-loaders-corpus-types-ReadOptions-store_raw_record}

```python
store_raw_record: bool = False
```

###### `agrag.loaders.corpus.types.ReadOptions.store_text` \{#agrag-loaders-corpus-types-ReadOptions-store_text}

```python
store_text: bool = True
```

###### `agrag.loaders.corpus.types.ReadOptions.text_column` \{#agrag-loaders-corpus-types-ReadOptions-text_column}

```python
text_column: str | None = None
```

###### `agrag.loaders.corpus.types.ReadOptions.title_column` \{#agrag-loaders-corpus-types-ReadOptions-title_column}

```python
title_column: str | None = None
```

##### `agrag.loaders.corpus.types.SourceRef` \{#agrag-loaders-corpus-types-SourceRef}

```python
SourceRef(uri:str, extension:str, byte_size:int | None = None, mime_type:str | None = None, modified_at:datetime | None = None) -> None
```

A locatable input, before any bytes are read.

**Attributes:**

- [**uri**](#agrag-loaders-corpus-types-SourceRef-uri) (<code>str</code>) – The location of the source, as the caller gave it.
- [**extension**](#agrag-loaders-corpus-types-SourceRef-extension) (<code>str</code>) – The lowercased file extension, with its leading dot.
- [**byte_size**](#agrag-loaders-corpus-types-SourceRef-byte_size) (<code>int | None</code>) – The size of the source in bytes. `None` when the backend cannot
  cheaply stat the source.
- [**mime_type**](#agrag-loaders-corpus-types-SourceRef-mime_type) (<code>str | None</code>) – The detected MIME type, when the loader can detect one.
- [**modified_at**](#agrag-loaders-corpus-types-SourceRef-modified_at) (<code>datetime | None</code>) – The last-modified time of the source, when the backend reports it.

###### `agrag.loaders.corpus.types.SourceRef.byte_size` \{#agrag-loaders-corpus-types-SourceRef-byte_size}

```python
byte_size: int | None = None
```

###### `agrag.loaders.corpus.types.SourceRef.extension` \{#agrag-loaders-corpus-types-SourceRef-extension}

```python
extension: str
```

###### `agrag.loaders.corpus.types.SourceRef.mime_type` \{#agrag-loaders-corpus-types-SourceRef-mime_type}

```python
mime_type: str | None = None
```

###### `agrag.loaders.corpus.types.SourceRef.modified_at` \{#agrag-loaders-corpus-types-SourceRef-modified_at}

```python
modified_at: datetime | None = None
```

###### `agrag.loaders.corpus.types.SourceRef.uri` \{#agrag-loaders-corpus-types-SourceRef-uri}

```python
uri: str
```

### `agrag.loaders.docling` \{#agrag-loaders-docling}

The docling loader package.

Importing this package registers `DoclingLoader` with the corpus registry. The core
loaders win by default for Markdown, HTML, and CSV; docling wins for PDF, DOCX, PPTX,
images, AsciiDoc, and XML.

**Modules:**

- [**loader**](#agrag-loaders-docling-loader) – Docling-backed loader for PDF, DOCX, PPTX, and image sources.

**Classes:**

- [**DoclingLoader**](#agrag-loaders-docling-DoclingLoader) – Reads documents with the docling library.

#### `agrag.loaders.docling.DoclingLoader` \{#agrag-loaders-docling-DoclingLoader}

Bases: <code>[ProseLoader](#agrag-loaders-corpus-base-ProseLoader)</code>

Reads documents with the docling library.

This loader registers for the PDF, DOCX, PPTX, and image formats, plus the Markdown,
HTML, CSV, AsciiDoc, and XML formats it can also parse. It wins by default only for
the
formats no core loader claims.

**Attributes:**

- [**extensions**](#agrag-loaders-docling-DoclingLoader-extensions) – Every format docling can read.
- [**extra**](#agrag-loaders-docling-DoclingLoader-extra) – The package extra required to use this loader.

**Functions:**

- [**load**](#agrag-loaders-docling-DoclingLoader-load) – Yield one prose Document parsed by docling.

##### `agrag.loaders.docling.DoclingLoader.extensions` \{#agrag-loaders-docling-DoclingLoader-extensions}

```python
extensions = frozenset(_DOCLING_FORMATS.keys())
```

##### `agrag.loaders.docling.DoclingLoader.extra` \{#agrag-loaders-docling-DoclingLoader-extra}

```python
extra = 'docling'
```

##### `agrag.loaders.docling.DoclingLoader.family` \{#agrag-loaders-docling-DoclingLoader-family}

```python
family = DocumentFamily.PROSE
```

##### `agrag.loaders.docling.DoclingLoader.load` \{#agrag-loaders-docling-DoclingLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one prose Document parsed by docling.

The content hash comes from the raw source bytes, not from docling's parsed
output,
because the parsed output can change between docling versions and runs.

**Parameters:**

- **source** (<code>[SourceRef](#agrag-loaders-corpus-types-SourceRef)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](#agrag-loaders-corpus-types-ReadOptions)</code>) – The read options.
- **start_at** (<code>int</code>) – Ignored by prose loaders.

**Yields:**

- <code>[Document](common.md#agrag-common-data_models-document-Document)</code> – One Document holding docling's Markdown export of the source.

**Raises:**

- <code>[MissingExtraError](#agrag-loaders-corpus-errors-MissingExtraError)</code> – The docling extra is not installed.
- <code>[DocumentTooLargeError](#agrag-loaders-corpus-errors-DocumentTooLargeError)</code> – The source is larger than the configured byte
  limit.
- <code>[DocumentConversionError](#agrag-loaders-corpus-errors-DocumentConversionError)</code> – Docling could not parse or convert the source.
- <code>ValueError</code> – `opts.max_document_bytes` is not a positive integer.

##### `agrag.loaders.docling.DoclingLoader.mime_types` \{#agrag-loaders-docling-DoclingLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```

#### `agrag.loaders.docling.loader` \{#agrag-loaders-docling-loader}

Docling-backed loader for PDF, DOCX, PPTX, and image sources.

Importing this module does not import the docling library. The loader imports docling
inside `load` so that the rest of the package works without the `docling` extra
installed. The registry raises `MissingExtraError` when a source needs this loader but
the extra is missing.

**Classes:**

- [**DoclingLoader**](#agrag-loaders-docling-loader-DoclingLoader) – Reads documents with the docling library.

##### `agrag.loaders.docling.loader.DoclingLoader` \{#agrag-loaders-docling-loader-DoclingLoader}

Bases: <code>[ProseLoader](#agrag-loaders-corpus-base-ProseLoader)</code>

Reads documents with the docling library.

This loader registers for the PDF, DOCX, PPTX, and image formats, plus the Markdown,
HTML, CSV, AsciiDoc, and XML formats it can also parse. It wins by default only for
the
formats no core loader claims.

**Attributes:**

- [**extensions**](#agrag-loaders-docling-loader-DoclingLoader-extensions) – Every format docling can read.
- [**extra**](#agrag-loaders-docling-loader-DoclingLoader-extra) – The package extra required to use this loader.

**Functions:**

- [**load**](#agrag-loaders-docling-loader-DoclingLoader-load) – Yield one prose Document parsed by docling.

###### `agrag.loaders.docling.loader.DoclingLoader.extensions` \{#agrag-loaders-docling-loader-DoclingLoader-extensions}

```python
extensions = frozenset(_DOCLING_FORMATS.keys())
```

###### `agrag.loaders.docling.loader.DoclingLoader.extra` \{#agrag-loaders-docling-loader-DoclingLoader-extra}

```python
extra = 'docling'
```

###### `agrag.loaders.docling.loader.DoclingLoader.family` \{#agrag-loaders-docling-loader-DoclingLoader-family}

```python
family = DocumentFamily.PROSE
```

###### `agrag.loaders.docling.loader.DoclingLoader.load` \{#agrag-loaders-docling-loader-DoclingLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one prose Document parsed by docling.

The content hash comes from the raw source bytes, not from docling's parsed
output,
because the parsed output can change between docling versions and runs.

**Parameters:**

- **source** (<code>[SourceRef](#agrag-loaders-corpus-types-SourceRef)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](#agrag-loaders-corpus-types-ReadOptions)</code>) – The read options.
- **start_at** (<code>int</code>) – Ignored by prose loaders.

**Yields:**

- <code>[Document](common.md#agrag-common-data_models-document-Document)</code> – One Document holding docling's Markdown export of the source.

**Raises:**

- <code>[MissingExtraError](#agrag-loaders-corpus-errors-MissingExtraError)</code> – The docling extra is not installed.
- <code>[DocumentTooLargeError](#agrag-loaders-corpus-errors-DocumentTooLargeError)</code> – The source is larger than the configured byte
  limit.
- <code>[DocumentConversionError](#agrag-loaders-corpus-errors-DocumentConversionError)</code> – Docling could not parse or convert the source.
- <code>ValueError</code> – `opts.max_document_bytes` is not a positive integer.

###### `agrag.loaders.docling.loader.DoclingLoader.mime_types` \{#agrag-loaders-docling-loader-DoclingLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```

### `agrag.loaders.registry` \{#agrag-loaders-registry}

The extension-to-loader registry.

**Classes:**

- [**LoaderRegistry**](#agrag-loaders-registry-LoaderRegistry) – Maps a source extension to the loader that reads it.

#### `agrag.loaders.registry.LoaderRegistry` \{#agrag-loaders-registry-LoaderRegistry}

```python
LoaderRegistry() -> None
```

Maps a source extension to the loader that reads it.

The registry picks a loader by file extension first. When more than one loader
claims
the same extension, the loader registered with `prefer=True` wins; when several
loaders
are preferred, the last preferred registration wins.

**Attributes:**

- **\_by_extension** (<code>dict\[str, list\[\_Entry\]\]</code>) – The registered loaders for each extension, in registration order.

**Functions:**

- [**for_source**](#agrag-loaders-registry-LoaderRegistry-for_source) – Return the default loader for a source.
- [**register**](#agrag-loaders-registry-LoaderRegistry-register) – Add a loader to the registry.

##### `agrag.loaders.registry.LoaderRegistry.for_source` \{#agrag-loaders-registry-LoaderRegistry-for_source}

```python
for_source(source:SourceRef) -> Loader
```

Return the default loader for a source.

**Parameters:**

- **source** (<code>[SourceRef](#agrag-loaders-corpus-types-SourceRef)</code>) – The source to find a loader for.

**Returns:**

- <code>[Loader](#agrag-loaders-corpus-base-Loader)</code> – The registered loader with the highest precedence for the source's
- <code>[Loader](#agrag-loaders-corpus-base-Loader)</code> – extension.

When the top-precedence loader needs a package extra that is not installed,
the first non-preferred loader for the extension whose extra (if any) is
installed is used instead, so an optional loader's absence falls back to the
core reader rather than always failing the source.

**Raises:**

- <code>[UnsupportedFormatError](#agrag-loaders-corpus-errors-UnsupportedFormatError)</code> – No loader claims the source's extension.
- <code>[MissingExtraError](#agrag-loaders-corpus-errors-MissingExtraError)</code> – A loader is mapped to the extension, but its package
  extra failed to import, and no fallback loader is available either.

##### `agrag.loaders.registry.LoaderRegistry.register` \{#agrag-loaders-registry-LoaderRegistry-register}

```python
register(loader:Loader, *, prefer:bool = False, extensions:set[str] | frozenset[str] | None = None) -> None
```

Add a loader to the registry.

Registering the same loader for the same extension more than once is a no-op, so
importing a package that registers loaders repeatedly stays safe.

**Parameters:**

- **loader** (<code>[Loader](#agrag-loaders-corpus-base-Loader)</code>) – The loader to register.
- **prefer** (<code>bool</code>) – Set this to True to make the loader the default for its extensions.
  Leave it False to register the loader only as an explicit, named option.
- **extensions** (<code>set\[str\] | frozenset\[str\] | None</code>) – Only register `loader` for these extensions. Defaults to every
  extension the loader advertises. A caller that wants different
  precedence per
  extension registers the same loader twice with different `extensions`
  sets.
