"""Record readers: CSV, TSV, JSON Lines, and JSON."""

import csv
import io
import json
from collections.abc import Iterator
from typing import BinaryIO

from agrag.common.data_models.document import Document, SourceFormat
from agrag.loaders.corpus.base import RecordLoader
from agrag.loaders.corpus.decode import decode_text
from agrag.loaders.corpus.errors import MalformedRecordError
from agrag.loaders.corpus.readers._common import (
    build_prose_document,
    build_record_document,
    read_within_limit,
    record_source_hash,
    source_title,
)
from agrag.loaders.corpus.types import CsvMode, JsonMode, ReadOptions, SourceRef


class CsvLoader(RecordLoader):
    """Reads CSV and TSV files as one document per row.

    Attributes:
        extensions: The ``.csv`` and ``.tsv`` extensions.
    """

    extensions = frozenset({".csv", ".tsv"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator:
        """Yield one record Document per row.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options. ``csv_delimiter`` overrides the separator.
            start_at: The record index to resume from.

        Yields:
            One Document per row, in file order.

        Raises:
            MalformedRecordError: A row fails to parse.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        if opts.csv_mode == CsvMode.TABLE:
            yield build_prose_document(
                source=source,
                text=decoded.text,
                encoding=decoded.encoding,
                source_format=SourceFormat.CSV,
                loader_name="csv",
                opts=opts,
                title=source_title(source),
            )
            return

        delimiter = opts.csv_delimiter or ("\t" if source.extension == ".tsv" else ",")
        source_hash = record_source_hash(raw)
        try:
            reader = csv.DictReader(
                io.StringIO(decoded.text), delimiter=delimiter, strict=True
            )
            for index, row in enumerate(reader):
                if index < start_at:
                    continue
                if row is None:
                    continue
                yield build_record_document(
                    source=source,
                    decoded=decoded,
                    source_format=SourceFormat.CSV,
                    loader_name="csv",
                    opts=opts,
                    record_index=index,
                    record=dict(row),
                    source_hash=source_hash,
                    title=str(index),
                )
        except csv.Error as exc:
            raise MalformedRecordError(f"Failed to parse {source.uri}: {exc}") from exc


class JsonlLoader(RecordLoader):
    """Reads JSON Lines files as one document per line.

    Attributes:
        extensions: The ``.jsonl`` and ``.ndjson`` extensions.
    """

    extensions = frozenset({".jsonl", ".ndjson"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator:
        """Yield one record Document per JSON object.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options.
            start_at: The record index to resume from.

        Yields:
            One Document per line, in file order.

        Raises:
            MalformedRecordError: A line is not valid JSON.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        if opts.json_mode == JsonMode.DOCUMENT:
            yield build_prose_document(
                source=source,
                text=decoded.text,
                encoding=decoded.encoding,
                source_format=SourceFormat.JSONL,
                loader_name="jsonl",
                opts=opts,
                title=source_title(source),
            )
            return

        source_hash = record_source_hash(raw)
        record_index = -1
        for line_no, raw_line in enumerate(decoded.text.split("\n")):
            line = raw_line.strip()
            if not line:
                continue
            record_index += 1
            if record_index < start_at:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MalformedRecordError(
                    f"Failed to parse line {line_no} of {source.uri}: {exc}"
                ) from exc
            yield self._document(
                source, decoded, opts, record_index, record, source_hash
            )

    @staticmethod
    def _document(source, decoded, opts, index, record, source_hash) -> Document:  # noqa: PLR0917
        """Build one record Document from a parsed JSON value.

        Args:
            source: The source the record came from.
            decoded: The decoded text and its metadata.
            opts: The read options.
            index: The 0-based line number.
            record: The parsed JSON value.
            source_hash: The hash of the whole source file.

        Returns:
            The built Document.
        """
        if isinstance(record, dict):
            return build_record_document(
                source=source,
                decoded=decoded,
                source_format=SourceFormat.JSONL,
                loader_name="jsonl",
                opts=opts,
                record_index=index,
                record=record,
                source_hash=source_hash,
                title=str(index),
            )
        return build_prose_document(
            source=source,
            text=json.dumps(record, ensure_ascii=False),
            encoding=decoded.encoding,
            source_format=SourceFormat.JSONL,
            loader_name="jsonl",
            opts=opts,
            title=str(index),
        )


class JsonLoader(RecordLoader):
    """Reads JSON files, disambiguating arrays from objects.

    Attributes:
        extensions: The ``.json`` extension.
    """

    extensions = frozenset({".json"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator:
        """Yield documents from a JSON source.

        A top-level array becomes one record Document per element, unless ``json_mode``
        is
        ``DOCUMENT``, which yields one prose Document holding the whole array. A
        top-level
        object becomes one prose Document.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options. ``json_mode`` overrides the sniff.
            start_at: The record index to resume from (arrays only).

        Yields:
            One or more Documents, in file order.

        Raises:
            MalformedRecordError: The source is not valid JSON.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        try:
            data = json.loads(decoded.text)
        except json.JSONDecodeError as exc:
            raise MalformedRecordError(f"Failed to parse {source.uri}: {exc}") from exc

        source_hash = record_source_hash(raw)
        if isinstance(data, list) and opts.json_mode != JsonMode.DOCUMENT:
            for index, element in enumerate(data):
                if index < start_at:
                    continue
                yield self._element(source, decoded, opts, index, element, source_hash)
            return

        if isinstance(data, list):
            text = json.dumps(data, ensure_ascii=False)
        elif isinstance(data, dict):
            text = (
                str(data.get(opts.text_column))
                if opts.text_column and opts.text_column in data
                else json.dumps(data, ensure_ascii=False)
            )
        else:
            text = json.dumps(data, ensure_ascii=False)
        yield build_prose_document(
            source=source,
            text=text,
            encoding=decoded.encoding,
            source_format=SourceFormat.JSON,
            loader_name="json",
            opts=opts,
            title=source_title(source),
        )

    @staticmethod
    def _element(source, decoded, opts, index, element, source_hash) -> Document:  # noqa: PLR0917
        """Build one record Document from a parsed JSON array element.

        Args:
            source: The source the element came from.
            decoded: The decoded text and its metadata.
            opts: The read options.
            index: The 0-based element position.
            element: The parsed JSON value.
            source_hash: The hash of the whole source file.

        Returns:
            The built Document.
        """
        if isinstance(element, dict):
            return build_record_document(
                source=source,
                decoded=decoded,
                source_format=SourceFormat.JSON,
                loader_name="json",
                opts=opts,
                record_index=index,
                record=element,
                source_hash=source_hash,
                title=str(index),
            )
        return build_prose_document(
            source=source,
            text=json.dumps(element, ensure_ascii=False),
            encoding=decoded.encoding,
            source_format=SourceFormat.JSON,
            loader_name="json",
            opts=opts,
            title=str(index),
        )
