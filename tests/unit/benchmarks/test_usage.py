"""Tests usage counting from spans: which spans count, and to which path.

The spans are real SDK spans made through the harness's own provider.
"""

import threading

from benchmarks.harness.record import PathUsage, read_trace
from benchmarks.harness.usage import (
    CORPUS_ATTRIBUTE,
    GRADE_SPAN,
    INGEST_SPAN,
    QUESTION_ATTRIBUTE,
    QUESTION_SPAN,
    start_tracing,
    summarize,
)
from tests.unit.benchmarks.fakes import llm_span


def _spans(tracing):
    return tracing.memory.get_finished_spans()


class TestSummarize:
    """Usage read from finished spans."""

    def test_counts_only_llm_kind_spans_and_sums_their_tokens(self, tmp_path):
        """Counts only llm kind spans and sums their tokens."""
        tracing = start_tracing(tmp_path / "t.jsonl.gz")
        with tracing.tracer.start_as_current_span("agrag.retrieval.search"):
            pass
        llm_span(tracing.tracer, prompt=10, completion=5)
        llm_span(tracing.tracer, prompt=1, completion=2)
        tracing.close()

        summary = summarize(_spans(tracing))

        assert summary.total == PathUsage(llm_calls=2, input_tokens=11, output_tokens=7)

    def test_a_span_takes_the_path_of_its_nearest_named_ancestor(self, tmp_path):
        """A span takes the path of its nearest named ancestor."""
        tracing = start_tracing(tmp_path / "t.jsonl.gz")
        tracer = tracing.tracer
        with tracer.start_as_current_span(
            INGEST_SPAN, attributes={CORPUS_ATTRIBUTE: "c"}
        ):
            with tracer.start_as_current_span("agrag.extraction.extract_chunk"):
                llm_span(tracer)
            with tracer.start_as_current_span("agrag.resolution.llm_verify"):
                llm_span(tracer)
        with (
            tracer.start_as_current_span(
                QUESTION_SPAN, attributes={QUESTION_ATTRIBUTE: "q"}
            ),
            tracer.start_as_current_span("agrag.retrieval.generate_cypher"),
        ):
            llm_span(tracer)
        with tracer.start_as_current_span("agrag.eval.judge"):
            llm_span(tracer)
        with tracer.start_as_current_span(GRADE_SPAN):
            llm_span(tracer)
        tracing.close()

        summary = summarize(_spans(tracing))

        assert {p: u.llm_calls for p, u in summary.by_path.items()} == {
            "agent": 1,
            "extraction": 1,
            "judge": 2,
            "other": 1,
        }
        assert summary.by_corpus["c"].usage.llm_calls == 2
        assert summary.by_question["q"].llm_calls == 1

    def test_a_span_without_prompt_tokens_makes_usage_incomplete(self, tmp_path):
        """A span without prompt tokens makes usage incomplete."""
        tracing = start_tracing(tmp_path / "t.jsonl.gz")
        llm_span(tracing.tracer, prompt=None)
        tracing.close()

        assert summarize(_spans(tracing)).usage_complete is False

    def test_counts_empty_extractions_per_corpus(self, tmp_path):
        """Counts empty extractions per corpus."""
        tracing = start_tracing(tmp_path / "t.jsonl.gz")
        tracer = tracing.tracer
        with tracer.start_as_current_span(
            INGEST_SPAN, attributes={CORPUS_ATTRIBUTE: "c"}
        ):
            for found in (0, 3, 0):
                with tracer.start_as_current_span(
                    "agrag.extraction.baml",
                    attributes={"agrag.entities_extracted": found},
                ):
                    pass
        tracing.close()

        assert summarize(_spans(tracing)).by_corpus["c"].empty_extractions == 2

    def test_retrieved_chunk_ids_keep_order_and_skip_other_kinds(self, tmp_path):
        """Retrieved chunk ids keep order and skip other kinds."""
        tracing = start_tracing(tmp_path / "t.jsonl.gz")
        tracer = tracing.tracer
        with tracer.start_as_current_span(
            QUESTION_SPAN, attributes={QUESTION_ATTRIBUTE: "q"}
        ):
            for ids, kinds in (
                (["a", "e1", "b"], ["Chunk", "Entity", "Chunk"]),
                (["b", "c"], ["Chunk", "Chunk"]),
            ):
                with tracer.start_as_current_span(
                    "agrag.retrieval.search",
                    attributes={"agrag.result_ids": ids, "agrag.result_kinds": kinds},
                ):
                    pass
        tracing.close()

        assert summarize(_spans(tracing)).by_question["q"].retrieved_chunk_ids == [
            "a",
            "b",
            "c",
        ]

    def test_provider_keeps_attributes_beyond_the_sdk_default_of_128(self, tmp_path):
        """Provider keeps attributes beyond the sdk default of 128."""
        tracing = start_tracing(tmp_path / "t.jsonl.gz")
        with tracing.tracer.start_as_current_span("s") as span:
            for index in range(300):
                span.set_attribute(f"k{index}", index)
        tracing.close()

        assert len(_spans(tracing)[0].attributes) == 300


class TestTraceFile:
    """The gzipped trace file."""

    def test_writes_one_json_batch_per_line_after_close(self, tmp_path):
        """Writes one json batch per line after close."""
        path = tmp_path / "t.jsonl.gz"
        tracing = start_tracing(path)
        llm_span(tracing.tracer)
        llm_span(tracing.tracer)
        tracing.close()

        batches = read_trace(path)

        assert len(batches) == 2
        span = batches[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["name"] == "llm"

    def test_spans_ended_on_many_threads_leave_every_line_readable(self, tmp_path):
        """Concurrent exports must not interleave inside the gzip stream."""
        path = tmp_path / "t.jsonl.gz"
        tracing = start_tracing(path)

        def work() -> None:
            for _ in range(100):
                llm_span(tracing.tracer)

        threads = [threading.Thread(target=work) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        tracing.close()

        assert len(read_trace(path)) == 800
