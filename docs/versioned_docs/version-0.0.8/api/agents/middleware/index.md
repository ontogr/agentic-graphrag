---
title: agrag.agents.middleware
sidebar_label: middleware
---

# `agrag.agents.middleware` \{#agrag-agents-middleware}

Middleware for composing configured chat models and capturing task events.

**Classes:**

- [**RoundRobinModelMiddleware**](RoundRobinModelMiddleware.md) – Rotate model requests across configured clients.
- [**RunState**](RunState.md) – Mutable facts accumulated by tools and middleware during one run.
- [**TaskEventMiddleware**](TaskEventMiddleware.md) – Persist assistant messages, tool calls and tool results as task events.

**Functions:**

- [**record_event_or_flag**](record_event_or_flag.md) – Append one event, retry it once, and flag the run if it still fails.
