"""Canary tests for the LLM span contract, one per LLM path.

Each test drives a public agrag entry point against a local OpenAI-compatible
server, so the real BAML runtime and a real ``ChatOpenAI`` speak real HTTP and
nothing below the HTTP boundary is mocked. A path whose spans changed shape, or
whose request span lost an attribute, fails here. The captured span tree is
written to a JSON artifact under ``reports/llm/`` for hand inspection.
"""

import importlib.util
from typing import Any
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.provenance import TextProvenance
from agrag.eval.judge import ChatModelJudge
from agrag.ingestion.community import generate_community_reports
from agrag.ingestion.extract import BAMLExtractor, ExtractionLLMSettings
from agrag.ingestion.merge import resolve_description
from agrag.ingestion.resolve.resolver import LLMVerify
from agrag.loaders.corpus.types import ErrorPolicy
from agrag.retrieval.retrievers.text2cypher import Text2CypherRetriever
from tests.integration.llm._local_llm import (
    COMPLETION_TOKENS,
    PROMPT_TOKENS,
    SECRET,
    LocalLLM,
    dead_base_url,
    env_for,
    span_tree_path,
    write_span_tree,
)


baml_missing = importlib.util.find_spec("baml_py") is None
pytestmark = pytest.mark.skipif(baml_missing, reason="baml extra not installed")

_DOC_ID = uuid4()


@pytest.fixture
def local() -> Any:
    """A running fake OpenAI-compatible endpoint."""
    server = LocalLLM()
    yield server
    server.close()


@pytest.fixture
def capture() -> tuple[Any, InMemorySpanExporter]:
    """Return a tracer and the exporter collecting its finished spans."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


def _chunk(text: str) -> Chunk:
    """Build a minimal Chunk."""
    return Chunk(
        document_id=_DOC_ID,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


def _names(spans: tuple[ReadableSpan, ...]) -> list[str]:
    """Return the span names in export order."""
    return [span.name for span in spans]


def _one(spans: tuple[ReadableSpan, ...], name: str) -> ReadableSpan:
    """Return the single finished span with that name."""
    matches = [span for span in spans if span.name == name]
    assert len(matches) == 1, f"expected one {name} span, got {len(matches)}"
    return matches[0]


def _ancestors(span: ReadableSpan, spans: tuple[ReadableSpan, ...]) -> list[str]:
    """Return the names of a span's ancestors, nearest first."""
    by_id = {item.context.span_id: item for item in spans}
    names: list[str] = []
    parent = span.parent
    seen: set[int] = set()
    while parent is not None and parent.span_id not in seen:
        seen.add(parent.span_id)
        holder = by_id.get(parent.span_id)
        if holder is None:
            break
        names.append(holder.name)
        parent = holder.parent
    return names


def _assert_request_span(span: ReadableSpan) -> None:
    """Assert the shared attribute contract of an ``agrag.llm.request`` span."""
    attributes = dict(span.attributes or {})
    assert attributes["openinference.span.kind"] == "LLM"
    assert attributes["llm.provider"] == "openai"
    assert attributes["agrag.llm.baml_provider"] == "openai-generic"
    assert attributes["llm.model_name"] == "requested-model-served"
    assert attributes["agrag.llm.requested_model"] == "requested-model"
    assert attributes["llm.token_count.prompt"] == PROMPT_TOKENS
    assert attributes["llm.token_count.completion"] == COMPLETION_TOKENS
    assert attributes["llm.token_count.total"] == PROMPT_TOKENS + COMPLETION_TOKENS
    assert attributes["input.mime_type"] == "application/json"
    assert attributes["output.mime_type"] == "application/json"
    assert span.kind.name == "CLIENT"


def _settings(local: LocalLLM, mode: str = "extract") -> ExtractionLLMSettings:
    """Return extraction settings pointing at the fake endpoint."""
    from agrag.llm.client_config import LLMClientConfig, RetryConfig  # noqa: PLC0415

    return ExtractionLLMSettings(
        clients=[
            LLMClientConfig(
                name="primary",
                provider="openai-generic",
                model="requested-model",
                api_key=SECRET,
                base_url=local.url(mode),
            )
        ],
        retry=RetryConfig(max_retries=0),
    )


def _settings_at(base_url: str) -> ExtractionLLMSettings:
    """Return extraction settings pointing at an arbitrary base URL."""
    from agrag.llm.client_config import LLMClientConfig, RetryConfig  # noqa: PLC0415

    return ExtractionLLMSettings(
        clients=[
            LLMClientConfig(
                name="primary",
                provider="openai-generic",
                model="requested-model",
                api_key=SECRET,
                base_url=base_url,
            )
        ],
        retry=RetryConfig(max_retries=0),
    )


def _entity(name: str, chunk_id: UUID) -> ExtractedEntity:
    """Build a minimal ExtractedEntity."""
    return ExtractedEntity(
        chunk_id=chunk_id,
        label="Person",
        text=name,
        char_start=0,
        char_end=len(name),
    )


def _chat_model(local: LocalLLM) -> Any:
    """Return a real ChatOpenAI pointed at the fake endpoint."""
    from langchain_openai import ChatOpenAI  # noqa: PLC0415

    return ChatOpenAI(
        model="requested-model",
        api_key=SECRET,
        base_url=local.url("ok"),
        max_retries=0,
    )


class _EmptyStore(Any):
    """A graph store whose every read returns nothing."""

    async def execute_read(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Return no rows, so the retriever produces no results."""
        return []

    async def get_schema(self, *args: Any, **kwargs: Any) -> Any:
        """Return the generic schema."""
        return GENERIC


def _assert_llm_subtree(spans: tuple[ReadableSpan, ...], root: str) -> ReadableSpan:
    """Assert the call > attempt > request subtree hangs under ``root``."""
    request = _one(spans, "agrag.llm.request")
    attempt = _one(spans, "agrag.llm.attempt")
    call = _one(spans, "agrag.llm.call")
    assert request.parent is not None
    assert request.parent.span_id == attempt.context.span_id
    assert attempt.parent is not None
    assert attempt.parent.span_id == call.context.span_id
    assert _ancestors(call, spans)[0] == root
    _assert_request_span(request)
    return call


class TestExtraction:
    """The extraction path nests the BAML subtree under its own span."""

    async def test_extraction_nests_the_llm_subtree(
        self, local: LocalLLM, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """A traced extractor emits baml > call > attempt > request."""
        tracer, exporter = capture
        extractor = BAMLExtractor(settings=_settings(local), tracer=tracer)

        await extractor.extract(
            _chunk("Meridian Health Group opened a clinic."), GENERIC
        )

        spans = exporter.get_finished_spans()
        assert _names(spans) == [
            "agrag.llm.request",
            "agrag.llm.attempt",
            "agrag.llm.call",
            "agrag.extraction.baml",
        ]
        call = _assert_llm_subtree(spans, "agrag.extraction.baml")
        assert (call.attributes or {})["agrag.llm.function"] == (
            "ExtractEntitiesAndRelations"
        )
        write_span_tree(span_tree_path("extraction.json"), spans)


class TestResolution:
    """The resolution path reports its counts, then nests the BAML subtree."""

    async def test_resolution_reports_counts_and_the_subtree(
        self, local: LocalLLM, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """LLMVerify opens one llm_verify span with the pair count."""
        tracer, exporter = capture
        chunk = _chunk("Ada Lovelace worked with Charles Babbage.")
        verifier = LLMVerify(
            chunks_by_id={chunk.id: chunk},
            settings=_settings(local, "verify"),
            tracer=tracer,
        )
        left = _entity("Ada Lovelace", chunk.id)
        right = _entity("Ada Lovelace", chunk.id)

        await verifier.compare(left, right)

        spans = exporter.get_finished_spans()
        verify = _one(spans, "agrag.resolution.llm_verify")
        assert (verify.attributes or {})["agrag.pair_count"] == 1
        call = _assert_llm_subtree(spans, "agrag.resolution.llm_verify")
        assert (call.attributes or {})["agrag.llm.function"] == "VerifyEntityMatches"
        write_span_tree(span_tree_path("resolution.json"), spans)


class TestMerge:
    """The merge path reports whether it summarized."""

    async def test_merge_records_a_successful_summary(
        self, local: LocalLLM, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """resolve_description marks agrag.summarized true on success."""
        tracer, exporter = capture

        value, conflicted, failure = await resolve_description(
            ["a clinic downtown", "a downtown clinic"],
            settings=_settings(local, "ok"),
            tracer=tracer,
        )

        assert conflicted is True
        assert failure is None
        spans = exporter.get_finished_spans()
        resolve = _one(spans, "agrag.merge.resolve_description")
        assert (resolve.attributes or {})["agrag.summarized"] is True
        assert (resolve.attributes or {})["agrag.description_count"] == 2
        call = _assert_llm_subtree(spans, "agrag.merge.resolve_description")
        assert (call.attributes or {})["agrag.llm.function"] == "SummarizeDescriptions"
        assert isinstance(value, str)
        write_span_tree(span_tree_path("merge.json"), spans)


class TestCommunity:
    """The community path hangs its subtree under the caller's span."""

    async def test_community_nests_the_subtree(
        self,
        local: LocalLLM,
        capture: tuple[Any, InMemorySpanExporter],
        monkeypatch: Any,
    ) -> None:
        """generate_community_reports traces the batch call it makes."""
        tracer, exporter = capture
        # The community path builds its registry from the environment.
        env_for(local, monkeypatch, "ok")
        ids = [uuid4(), uuid4()]
        entities = {
            each: Entity(id=each, label="Person", name=f"N{index}", properties={})
            for index, each in enumerate(ids)
        }
        community = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=ids,
            internal_weight=10.0,
        )

        with tracer.start_as_current_span("caller"):
            failures = await generate_community_reports(
                [community],
                entities,
                error_policy=ErrorPolicy.RAISE,
                tracer=tracer,
            )

        assert failures == []
        spans = exporter.get_finished_spans()
        call = _one(spans, "agrag.llm.call")
        # The batch span from the pipeline plan is the direct parent.
        assert _ancestors(call, spans) == ["agrag.community.report_batch", "caller"]
        assert (call.attributes or {})["agrag.llm.function"] == "SummarizeCommunities"
        assert len(local.received) == 1
        write_span_tree(span_tree_path("community.json"), spans)


class TestText2Cypher:
    """The text2cypher path traces generation under its own span."""

    async def test_text2cypher_nests_the_subtree(
        self,
        local: LocalLLM,
        capture: tuple[Any, InMemorySpanExporter],
        monkeypatch: Any,
    ) -> None:
        """A traced retriever records the repair flag and the BAML subtree."""
        tracer, exporter = capture
        env_for(local, monkeypatch, "cypher")
        retriever = Text2CypherRetriever(
            graph_store=_EmptyStore(), schema=GENERIC, tracer=tracer
        )

        assert await retriever.retrieve("who is Ada Lovelace?") == []

        spans = exporter.get_finished_spans()
        generate = _one(spans, "agrag.retrieval.generate_cypher")
        assert (generate.attributes or {})["agrag.is_repair"] is False
        call = _assert_llm_subtree(spans, "agrag.retrieval.generate_cypher")
        assert (call.attributes or {})["agrag.llm.function"] == "GenerateCypherQuery"
        write_span_tree(span_tree_path("text2cypher.json"), spans)


class TestJudge:
    """The judge path emits a judge span over an OpenInference LLM span."""

    async def test_judge_span_carries_token_counts(
        self, local: LocalLLM, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """A traced judge reports token counts under its own span."""
        tracer, exporter = capture
        judge = ChatModelJudge(_chat_model(local), "requested-model", tracer=tracer)

        await judge.a_generate("rate this")

        spans = exporter.get_finished_spans()
        judge_span = _one(spans, "agrag.eval.judge")
        assert (judge_span.attributes or {})["agrag.eval.judge_model"] == (
            "requested-model"
        )
        llm_spans = [
            span
            for span in spans
            if (span.attributes or {}).get("openinference.span.kind") == "LLM"
        ]
        assert len(llm_spans) == 1
        model = llm_spans[0]
        assert model.parent is not None
        assert model.parent.span_id == judge_span.context.span_id
        attributes = dict(model.attributes or {})
        assert attributes["llm.token_count.prompt"] == PROMPT_TOKENS
        assert attributes["llm.token_count.completion"] == COMPLETION_TOKENS
        write_span_tree(span_tree_path("judge.json"), spans)

        assert len(local.received) == 1


class TestCrossPathValueAgreement:
    """BAML and agent paths report consistent LLM span attributes."""

    async def test_both_paths_agree_on_provider_model_and_tokens(
        self, local: LocalLLM, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """One server, one reply, two paths: the attributes must match."""
        from agrag.agents.tracing import run_callbacks  # noqa: PLC0415

        tracer, exporter = capture
        extractor = BAMLExtractor(settings=_settings(local), tracer=tracer)
        await extractor.extract(
            _chunk("Meridian Health Group opened a clinic."), GENERIC
        )
        baml = dict(
            _one(exporter.get_finished_spans(), "agrag.llm.request").attributes or {}
        )  # type: ignore[arg-type]

        agent_exporter = InMemorySpanExporter()
        agent_provider = TracerProvider()
        agent_provider.add_span_processor(SimpleSpanProcessor(agent_exporter))
        await _chat_model(local).ainvoke(
            "hello", config={"callbacks": run_callbacks(agent_provider.get_tracer("t"))}
        )
        agent_llm = [
            span
            for span in agent_exporter.get_finished_spans()
            if (span.attributes or {}).get("openinference.span.kind") == "LLM"
        ]
        assert len(agent_llm) == 1
        agent = dict(agent_llm[0].attributes or {})

        for key in (
            "llm.provider",
            "llm.model_name",
            "llm.token_count.prompt",
            "llm.token_count.completion",
            "llm.token_count.total",
        ):
            assert agent[key] == baml[key], key

    async def test_both_paths_agree_against_a_real_endpoint(
        self, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """Both paths report model identity and internally consistent usage.

        The calls use different prompts, so their token counts need not match.
        """
        import os  # noqa: PLC0415

        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        from agrag.agents.tracing import run_callbacks  # noqa: PLC0415

        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY")
        model = os.environ.get("LLM_MODEL_ID")
        if not base_url or not api_key or not model:
            pytest.skip("LLM endpoint not configured")

        tracer, exporter = capture
        await BAMLExtractor(
            settings=ExtractionLLMSettings.from_openai_compatible_env(), tracer=tracer
        ).extract(_chunk("Meridian Health Group opened a clinic."), GENERIC)
        baml = dict(
            _one(exporter.get_finished_spans(), "agrag.llm.request").attributes or {}
        )  # type: ignore[arg-type]

        agent_exporter = InMemorySpanExporter()
        agent_provider = TracerProvider()
        agent_provider.add_span_processor(SimpleSpanProcessor(agent_exporter))
        await ChatOpenAI(
            model=model, api_key=api_key, base_url=base_url, max_retries=0
        ).ainvoke(
            "hello", config={"callbacks": run_callbacks(agent_provider.get_tracer("t"))}
        )
        agent_llm = [
            span
            for span in agent_exporter.get_finished_spans()
            if (span.attributes or {}).get("openinference.span.kind") == "LLM"
        ]
        assert len(agent_llm) == 1
        agent = dict(agent_llm[0].attributes or {})

        assert agent["llm.provider"] == baml["llm.provider"]
        assert agent["llm.model_name"] == baml["llm.model_name"]
        for attributes in (baml, agent):
            prompt_tokens = attributes["llm.token_count.prompt"]
            completion_tokens = attributes["llm.token_count.completion"]
            if not isinstance(prompt_tokens, int) or not isinstance(
                completion_tokens, int
            ):
                pytest.fail("LLM token counts must be integers")
            assert attributes["llm.token_count.total"] == (
                prompt_tokens + completion_tokens
            )


class TestNoSecretsInSpans:
    """The provider key never reaches a span, on any failure mode."""

    @staticmethod
    def _values(spans: tuple[ReadableSpan, ...]) -> list[str]:
        """Return every attribute and event attribute value as a string."""
        values: list[str] = []
        for span in spans:
            values.extend(str(value) for value in (span.attributes or {}).values())
            for event in span.events:
                values.extend(str(value) for value in (event.attributes or {}).values())
        return values

    def _assert_no_key(self, spans: tuple[ReadableSpan, ...]) -> None:
        """Assert the sentinel appears in no attribute or event value."""
        assert all(SECRET not in value for value in self._values(spans))

    async def test_a_successful_call_leaks_no_key(
        self, local: LocalLLM, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """A 200 records the bodies but never the authorization header."""
        tracer, exporter = capture
        extractor = BAMLExtractor(settings=_settings(local), tracer=tracer)

        await extractor.extract(
            _chunk("Meridian Health Group opened a clinic."), GENERIC
        )

        assert local.received, "the fake endpoint should have served a reply"
        self._assert_no_key(exporter.get_finished_spans())

    async def test_an_http_error_leaks_no_key(
        self, local: LocalLLM, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """A 500 records the error body, still without the key."""
        tracer, exporter = capture
        extractor = BAMLExtractor(settings=_settings(local, "500"), tracer=tracer)

        with pytest.raises(Exception):  # noqa: B017, PT011
            await extractor.extract(_chunk("Meridian Health Group."), GENERIC)

        self._assert_no_key(exporter.get_finished_spans())

    async def test_a_connection_failure_leaks_no_key(
        self, capture: tuple[Any, InMemorySpanExporter]
    ) -> None:
        """A dead port records the connection error without the key."""
        tracer, exporter = capture
        extractor = BAMLExtractor(settings=_settings_at(dead_base_url()), tracer=tracer)

        with pytest.raises(Exception):  # noqa: B017, PT011
            await extractor.extract(_chunk("Meridian Health Group."), GENERIC)

        self._assert_no_key(exporter.get_finished_spans())
