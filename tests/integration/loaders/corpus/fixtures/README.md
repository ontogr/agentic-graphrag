# Integration fixtures

Place a real PDF sample file here. The user supplies this before the docling-backed
integration tests (`tests/integration/loaders/docling_loader/`) can run.

Required files:

- `multi_page.pdf` — a PDF with content that crosses at least one page boundary, so a chunk
  spans two pages and produces more than one `PageSpan`.

Nothing in Phases 1-5 depends on this directory.
