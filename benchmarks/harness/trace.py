"""Trace export: gzipped span batches on disk, and upload for full runs."""

import gzip
import json
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from google.protobuf.json_format import MessageToDict
from huggingface_hub import HfApi
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from benchmarks.harness.record import TRACE_NAME, TraceRef, sha256_file


class GzipJsonlSpanExporter(SpanExporter):
    """Writes each exported batch as one line of OTLP protobuf JSON.

    The file is gzipped and flushed after each batch, so a run in progress can be
    read up to its last batch. Call ``shutdown`` to finish it. Spans end on many
    threads and a gzip stream is not thread safe, so writes take a lock.
    """

    def __init__(self, path: Path) -> None:
        """Open ``path`` for writing, creating its parent directory."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = gzip.open(path, "wt", encoding="utf-8")  # noqa: SIM115
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Write one batch as one line."""
        batch = MessageToDict(encode_spans(spans))
        line = json.dumps(batch, separators=(",", ":")) + "\n"
        with self._lock:
            self._file.write(line)
            self._file.flush()
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Close the file."""
        with self._lock:
            self._file.close()


def upload_trace(
    path: Path, *, repo: str, run_id: str, api: Any | None = None
) -> TraceRef:
    """Upload a trace to a private Hugging Face dataset repo.

    Args:
        path: The gzipped trace.
        repo: The dataset repo id. It is created private when it does not exist.
        run_id: The run id, which names the folder in the repo.
        api: A ``HfApi``, for tests.

    Returns:
        The trace reference for the record.
    """
    api = api or HfApi()
    api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    path_in_repo = f"runs/{run_id}/{TRACE_NAME}"
    commit = api.upload_file(
        path_or_fileobj=str(path),
        path_in_repo=path_in_repo,
        repo_id=repo,
        repo_type="dataset",
    )
    return TraceRef(
        repo=repo,
        revision=commit.oid,
        path=path_in_repo,
        sha256=sha256_file(path),
    )
