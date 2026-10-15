---
title: agrag.agents.tools.core
sidebar_label: core
---

# `agrag.agents.tools.core` \{#agrag-agents-tools-core}

Tools for scoped evidence, task progress and decisions.

Tool calls and results are recorded as task events by the middleware, so these
tools only count the budget and record the events they create themselves.

**Functions:**

- [**make_core_tools**](make_core_tools.md) – Bind evidence and memory tools to a single task and trusted scope.
