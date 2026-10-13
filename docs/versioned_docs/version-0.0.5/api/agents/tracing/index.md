---
title: agrag.agents.tracing
sidebar_label: tracing
---

# `agrag.agents.tracing` \{#agrag-agents-tracing}

Per-run OpenInference tracing for agent runs.

`build_agent` takes an optional OpenTelemetry `Tracer`. Each `ainvoke`
passes a fresh OpenInference callback built from it, so no global tracer
provider or instrumentation is installed. deepagents forwards the parent's
callbacks to the researcher and verifier subagents, so their tool and model
calls appear in the same trace.

**Functions:**

- [**require_tracing**](require_tracing.md) – Raise a typed error when tracing dependencies are unavailable.
- [**run_callbacks**](run_callbacks.md) – Return the callbacks for one agent run.
- [**tool_span_context**](tool_span_context.md) – Return a context in which the running tool's OpenInference span is current.
