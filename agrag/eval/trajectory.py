"""Agent trajectory evaluation: read runs, check structure, judge quality.

A trajectory is the ordered tool and model steps of one agent run, read from
its OpenTelemetry spans (see ``agrag.agents.tracing``). Structural rules over
it are deterministic; task completion and trajectory quality use an LLM judge.
"""

import json
from collections.abc import Sequence
from typing import Any, Literal

from agentevals.trajectory import (
    create_trajectory_llm_as_judge,
    create_trajectory_match_evaluator,
)
from deepeval.metrics import BaseMetric, TaskCompletionMetric
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, ToolCall
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import Tracer
from pydantic import BaseModel

from agrag.eval.adapter import ScoreMetric, ScoreResult
from agrag.eval.repeat import MedianOfN


class Step(BaseModel):
    """One tool or model step of an agent run.

    Attributes:
        kind: ``"tool"`` for a tool call, ``"llm"`` for a model call.
        name: The tool name, or the span name for a model call.
        args: The parsed ``input.value`` span attribute.
        output: The step's output text, unwrapped from its tool message.
        span_id: The span id as hex.
        parent_ids: The ancestor span ids, nearest first, as hex.
        started: Start time in nanoseconds.
        ended: End time in nanoseconds.
        subagent: The ``subagent_type`` of the nearest ancestor ``task``
            span, or None for a planner step.
    """

    kind: Literal["tool", "llm"]
    name: str
    args: dict[str, Any]
    output: str
    span_id: str
    parent_ids: list[str]
    started: int
    ended: int
    subagent: str | None


class Trajectory(BaseModel):
    """The ordered steps of one agent run.

    Attributes:
        steps: The run's tool and model steps in start order.
    """

    steps: list[Step]


def _kind(span: ReadableSpan) -> Literal["tool", "llm"] | None:
    """Return the step kind for a span, or None when it is not a step."""
    attributes = span.attributes or {}
    kind = attributes.get("openinference.span.kind")
    if kind == "TOOL":
        return "tool"
    if kind == "LLM":
        return "llm"
    return None


def _is_task(span: ReadableSpan) -> bool:
    """Tell a delegation span from any other tool span."""
    attributes = span.attributes or {}
    return str(attributes.get("tool.name", span.name)) == "task"


def _read_args(raw: Any) -> dict[str, Any]:
    """Parse ``input.value`` as JSON, keeping raw text when it is not JSON."""
    if raw is None:
        return {}
    text = raw if isinstance(raw, str) else str(raw)
    try:
        parsed = json.loads(text)
    except ValueError:
        return {"input": text}
    return parsed if isinstance(parsed, dict) else {"input": text}


def _read_output(raw: Any) -> str:
    """Unwrap a serialized tool message, keeping raw text otherwise.

    A tool span's ``output.value`` is a serialized ``ToolMessage``, so the
    step output is its ``data.content``. Anything else is kept as is.
    """
    if raw is None:
        return ""
    text = raw if isinstance(raw, str) else str(raw)
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if isinstance(parsed, dict):
        data = parsed.get("data")
        if isinstance(data, dict) and "content" in data:
            content = data["content"]
            return content if isinstance(content, str) else json.dumps(content)
    return text


def _parent_ids(span: ReadableSpan, by_id: dict[int, ReadableSpan]) -> list[str]:
    """Return every ancestor span id, nearest first.

    The walk follows every span, including dropped ``CHAIN`` spans, so a step
    nested under middleware spans still records its full chain.
    """
    chain: list[str] = []
    seen: set[int] = set()
    if span.context is not None:
        seen.add(span.context.span_id)
    parent = span.parent
    while parent is not None and parent.span_id not in seen:
        seen.add(parent.span_id)
        chain.append(f"{parent.span_id:016x}")
        holder = by_id.get(parent.span_id)
        parent = holder.parent if holder is not None else None
    return chain


def _subagent(span: ReadableSpan, by_id: dict[int, ReadableSpan]) -> str | None:
    """Return the ``subagent_type`` of the nearest ancestor ``task`` span."""
    seen: set[int] = set()
    current = span
    while True:
        parent = current.parent
        if parent is None or parent.span_id in seen:
            return None
        seen.add(parent.span_id)
        holder = by_id.get(parent.span_id)
        if holder is None:
            return None
        if _is_task(holder):
            args = _read_args((holder.attributes or {}).get("input.value"))
            subagent_type = args.get("subagent_type")
            return str(subagent_type) if subagent_type is not None else None
        current = holder


def _read_step(span: ReadableSpan, by_id: dict[int, ReadableSpan]) -> Step:
    """Read one kept span as a trajectory step."""
    attributes = span.attributes or {}
    kind = _kind(span)
    name = str(attributes.get("tool.name", span.name)) if kind == "tool" else span.name
    context = span.context
    return Step(
        kind=kind or "tool",
        name=name,
        args=_read_args(attributes.get("input.value")),
        output=_read_output(attributes.get("output.value")),
        span_id=f"{context.span_id:016x}" if context is not None else "",
        parent_ids=_parent_ids(span, by_id),
        started=span.start_time or 0,
        ended=span.end_time or 0,
        subagent=_subagent(span, by_id),
    )


def read_trajectory(spans: Sequence[ReadableSpan]) -> Trajectory:
    """Read the tool and model steps from finished spans.

    Keeps ``TOOL`` and ``LLM`` spans, drops ``CHAIN`` spans, and orders steps
    by start time rather than export order. A step's ``subagent`` is the
    ``subagent_type`` of its nearest ancestor ``task`` span, or None for a
    planner step.

    Args:
        spans: The finished spans of one traced agent run.

    Returns:
        The run's trajectory in start order.
    """
    by_id: dict[int, ReadableSpan] = {}
    for span in spans:
        if span.context is not None:
            by_id[span.context.span_id] = span
    kept = [span for span in spans if _kind(span) is not None]
    kept.sort(key=lambda span: (span.start_time or 0, span.end_time or 0, span.name))
    return Trajectory(steps=[_read_step(span, by_id) for span in kept])


class SpanCapture:
    """Capture one agent run's spans for ``read_trajectory``.

    Use as a context manager around ``agent.ainvoke`` and read the run with
    ``trajectory()`` after. Each capture has its own provider and exporter,
    so captures never share spans and the global provider is unchanged.

    Example:
        with SpanCapture() as capture:
            agent = build_agent(engine, settings, tracer=capture.tracer)
            result = await agent.ainvoke({"messages": [...]})
        trajectory = capture.trajectory()
    """

    def __init__(self) -> None:
        """Create a private provider and exporter."""
        from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: PLC0415
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: PLC0415
            InMemorySpanExporter,
        )

        self._exporter = InMemorySpanExporter()
        self._provider = TracerProvider()
        self._provider.add_span_processor(SimpleSpanProcessor(self._exporter))

    @property
    def tracer(self) -> Tracer:
        """The tracer to pass as ``tracer=`` to ``build_agent``."""
        return self._provider.get_tracer("agrag.eval")

    def trajectory(self) -> Trajectory:
        """Read the captured spans as a trajectory."""
        return read_trajectory(self._exporter.get_finished_spans())

    def __enter__(self) -> "SpanCapture":
        """Return this capture."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Shut down the private provider."""
        self._provider.shutdown()


def trajectory_case(question: str, answer: str, trajectory: Trajectory) -> LLMTestCase:
    """Build the test case every trajectory metric scores.

    ``tools_called`` holds every ``TOOL`` step, planner and researcher, as a
    ``ToolCall``. ``metadata["trajectory"]`` holds the serialized trajectory
    the deterministic metrics read.

    Args:
        question: The question the agent answered.
        answer: The agent's final answer.
        trajectory: The run's trajectory from ``read_trajectory``.

    Returns:
        The test case with the answer, the tool calls and the trajectory.
    """
    return LLMTestCase(
        input=question,
        actual_output=answer,
        tools_called=[
            ToolCall(name=step.name, input_parameters=step.args, output=step.output)
            for step in trajectory.steps
            if step.kind == "tool"
        ],
        metadata={"trajectory": trajectory.model_dump()},
    )


def _case_trajectory(test_case: LLMTestCase) -> Trajectory:
    """Read the trajectory from a case built by ``trajectory_case``."""
    metadata = test_case.metadata or {}
    raw = metadata.get("trajectory")
    if raw is None:
        raise ValueError("trajectory metric needs a case built by trajectory_case")
    return Trajectory.model_validate(raw)


def _task_spans(trajectory: Trajectory, subagent_type: str) -> list[Step]:
    """Return the delegation spans for one subagent type."""
    return [
        step
        for step in trajectory.steps
        if step.name == "task" and step.args.get("subagent_type") == subagent_type
    ]


def _tool_calls_message(tool_steps: list[Step]) -> dict[str, Any]:
    """Build one assistant message with a tool call per step, in order."""
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": f"call-{index}",
                "type": "function",
                "function": {
                    "name": step.name,
                    "arguments": json.dumps(step.args),
                },
            }
            for index, step in enumerate(tool_steps)
        ],
    }


def _trajectory_messages(question: str, trajectory: Trajectory) -> list[dict[str, Any]]:
    """Build the judge's view: the question, then each tool call in order."""
    tool_steps = [step for step in trajectory.steps if step.kind == "tool"]
    return [{"role": "user", "content": question}, _tool_calls_message(tool_steps)]


_TRAJECTORY_QUALITY_PROMPT = (
    "You grade the trajectory of an AI agent that answers questions from "
    "a knowledge graph. Read the question and the tool calls the agent made, "
    "in order, then score the trajectory from 0 to 1.\n\n"
    "Score high when the steps follow logically from the question, the "
    "researcher's tool calls are targeted at the question, and the verifier "
    "was consulted before the answer. Score low when the steps wander, "
    "repeat without new information, or skip verification. Shorter is not "
    "better and longer is not better: judge only whether the work answers "
    "the question.\n\n"
    'Reply with ONLY a JSON object of the form {{"score": <number from 0 '
    'to 1>, "reasoning": <one sentence>}}, and no other text.\n\n'
    "Question and trajectory:\n{outputs}"
)


class _ScoreRepairRunnable:
    """Structured judge that maps a bare numeric score into a score object.

    Some OpenAI-compatible endpoints answer a score prompt with a bare
    number instead of the requested object. The trajectory judge needs
    ``score`` and ``reasoning`` keys, so a numeric reply becomes that
    object with empty reasoning. Anything else passes through, and the
    judge call fails as usual when it is unparsable.
    """

    def __init__(self, structured: Any) -> None:
        """Bind the structured runnable to repair."""
        self._structured = structured

    def invoke(self, prompt_input: Any, config: Any = None, **kwargs: Any) -> Any:
        """Run the judge, repairing a bare numeric reply."""
        response = self._structured.invoke(prompt_input, config, **kwargs)
        if isinstance(response, (dict, bool)):
            return response
        if isinstance(response, (int, float)):
            return {"score": float(response), "reasoning": ""}
        return response


class _ScoreRepairModel(BaseChatModel):
    """Chat model that repairs bare-number structured judge replies.

    Wraps the judge's chat model for the trajectory judge only. Structured
    calls go to the wrapped model with the caller's own method; direct calls
    run the wrapped model as is.
    """

    wrapped: Any

    @property
    def _llm_type(self) -> str:
        """Name the wrapper model type."""
        return "score-repair"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Run the wrapped model and return its reply."""
        message = self.wrapped.invoke(messages)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        """Return the wrapped structured judge with numeric repair."""
        return _ScoreRepairRunnable(
            self.wrapped.with_structured_output(schema, **kwargs)
        )


def verifier_before_answer_metric(*, threshold: float = 0.5) -> ScoreMetric:
    """Build the metric that the verifier ran before the answer.

    Passes when the planner's last ``LLM`` span starts after at least one
    verifier ``task`` span ended. Scores 1.0 or 0.0.

    Args:
        threshold: The minimum score that counts as success.

    Returns:
        A ``ScoreMetric`` that scores verifier-before-answer.
    """

    def scorer(test_case: LLMTestCase) -> ScoreResult:
        trajectory = _case_trajectory(test_case)
        verifier_ends = [step.ended for step in _task_spans(trajectory, "verifier")]
        if not verifier_ends:
            return ScoreResult(0.0, "No verifier task span ran before the answer.", {})
        planner_starts = [
            step.started
            for step in trajectory.steps
            if step.kind == "llm" and step.subagent is None
        ]
        if not planner_starts:
            return ScoreResult(0.0, "No planner LLM span wrote an answer.", {})
        if any(end <= max(planner_starts) for end in verifier_ends):
            return ScoreResult(1.0, "The verifier ran before the answer.", {})
        return ScoreResult(0.0, "The verifier finished after the answer started.", {})

    return ScoreMetric("Verifier before answer", scorer, threshold)


def retry_budget_metric(max_attempts: int, *, threshold: float = 0.5) -> ScoreMetric:
    """Build the metric that retries stay within budget.

    Counts researcher ``task`` spans starting after the first verifier
    ``task`` span ended. A call the limiter blocks leaves no span, so only
    executed delegations count. Scores 1.0 or 0.0.

    Args:
        max_attempts: How many researcher retries after verification pass.
        threshold: The minimum score that counts as success.

    Returns:
        A ``ScoreMetric`` that scores the retry budget.
    """

    def scorer(test_case: LLMTestCase) -> ScoreResult:
        trajectory = _case_trajectory(test_case)
        verifier_ends = sorted(
            step.ended for step in _task_spans(trajectory, "verifier")
        )
        if not verifier_ends:
            return ScoreResult(
                1.0, "No verifier span ran, so no retry was counted.", {}
            )
        retries = sum(
            1
            for step in _task_spans(trajectory, "researcher")
            if step.started > verifier_ends[0]
        )
        if retries <= max_attempts:
            return ScoreResult(
                1.0,
                f"{retries} researcher retries after verification "
                f"(budget {max_attempts}).",
                {},
            )
        return ScoreResult(
            0.0,
            f"{retries} researcher retries after verification exceed "
            f"the budget of {max_attempts}.",
            {},
        )

    return ScoreMetric("Retry budget", scorer, threshold)


def expected_tools_metric(
    names: Sequence[str], *, threshold: float = 0.5
) -> ScoreMetric:
    """Build the metric that the run called every expected tool.

    Compares the trajectory's tool calls with the expected names as a
    superset, ignoring arguments: extra tools do not matter, a missing name
    fails. Scores 1.0 or 0.0.

    Args:
        names: The tool names the run must include.
        threshold: The minimum score that counts as success.

    Returns:
        A ``ScoreMetric`` that scores tool presence.
    """
    reference = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": f"expected-{index}",
                    "type": "function",
                    "function": {"name": name, "arguments": "{}"},
                }
                for index, name in enumerate(names)
            ],
        }
    ]
    evaluator = create_trajectory_match_evaluator(
        trajectory_match_mode="superset", tool_args_match_mode="ignore"
    )

    def scorer(test_case: LLMTestCase) -> ScoreResult:
        trajectory = _case_trajectory(test_case)
        tool_steps = [step for step in trajectory.steps if step.kind == "tool"]
        outputs = [_tool_calls_message(tool_steps)]
        result = evaluator(outputs=outputs, reference_outputs=reference)
        if isinstance(result, list):
            result = result[0]
        called = [step.name for step in tool_steps]
        if bool(result["score"]):
            return ScoreResult(
                1.0,
                f"All {len(names)} expected tools were called.",
                {"called": called},
            )
        missing = [name for name in names if name not in called]
        return ScoreResult(
            0.0,
            f"Missing tools: {', '.join(missing)}. "
            f"Called: {', '.join(called) or 'none'}.",
            {"called": called, "missing": missing},
        )

    return ScoreMetric("Expected tools", scorer, threshold)


def task_completion(judge: DeepEvalBaseLLM, *, threshold: float = 0.5) -> BaseMetric:
    """Build the judged metric for task completion.

    Scores whether the run achieved the question's goal, from the question,
    the answer and the tool calls. The judge runs three times and the median
    reports, so one noisy judgment cannot flip the result.

    Args:
        judge: The judge model.
        threshold: The minimum score that counts as success.

    Returns:
        The task completion metric.
    """
    return MedianOfN(TaskCompletionMetric(model=judge, threshold=threshold))


def trajectory_quality(judge: DeepEvalBaseLLM, *, threshold: float = 0.5) -> BaseMetric:
    """Build the judged metric for trajectory quality.

    Scores whether the steps follow logically from the question, with no
    reference trajectory. The judge runs three times and the median reports.

    Args:
        judge: The judge model. Its chat model grades the trajectory.
        threshold: The minimum score that counts as success.

    Returns:
        The trajectory quality metric.

    Raises:
        TypeError: The judge holds no LangChain chat model.
    """
    chat_model = judge.model
    if not isinstance(chat_model, BaseChatModel):
        raise TypeError("trajectory_quality needs a judge holding a chat model")
    evaluator = create_trajectory_llm_as_judge(
        prompt=_TRAJECTORY_QUALITY_PROMPT,
        judge=_ScoreRepairModel(wrapped=chat_model),
        feedback_key="trajectory_quality",
        continuous=True,
    )

    def scorer(test_case: LLMTestCase) -> ScoreResult:
        trajectory = _case_trajectory(test_case)
        messages = _trajectory_messages(test_case.input, trajectory)
        result = evaluator(outputs=messages)
        if isinstance(result, list):
            result = result[0]
        return ScoreResult(
            float(result["score"]),
            str(result.get("comment") or ""),
            {"key": result.get("key")},
        )

    return MedianOfN(ScoreMetric("Trajectory quality", scorer, threshold))
