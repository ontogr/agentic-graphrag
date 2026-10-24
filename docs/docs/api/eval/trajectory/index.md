---
title: agrag.eval.trajectory
sidebar_label: trajectory
---

# `agrag.eval.trajectory` \{#agrag-eval-trajectory}

Agent trajectory evaluation: read runs, check structure, judge quality.

A trajectory is the ordered tool and model steps of one agent run, read from
its OpenTelemetry spans (see `agrag.agents.tracing`). Structural rules over
it are deterministic; task completion and trajectory quality use an LLM judge.

**Classes:**

- [**SpanCapture**](SpanCapture.md) – Capture one agent run's spans for `read_trajectory`.
- [**Step**](Step.md) – One tool or model step of an agent run.
- [**Trajectory**](Trajectory-ref.md) – The ordered steps of one agent run.

**Functions:**

- [**expected_tools_metric**](expected_tools_metric.md) – Build the metric that the run made every expected tool call, in order.
- [**read_trajectory**](read_trajectory.md) – Read the tool and model steps from finished spans.
- [**task_completion**](task_completion.md) – Build the judged metric for task completion.
- [**trajectory_case**](trajectory_case.md) – Build the test case every trajectory metric scores.
- [**trajectory_quality**](trajectory_quality.md) – Build the judged metric for trajectory quality.
