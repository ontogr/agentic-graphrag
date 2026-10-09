---
title: agrag.agents.subagents
sidebar_label: subagents
---

# `agrag.agents.subagents` \{#agrag-agents-subagents}

Subagent specs for the researcher and verifier roles.

Each spec is a SubAgent-shaped dict for `create_deep_agent`'s
`subagents=` list. Both roles run isolated: they see only the task
description the planner delegates with, so each spec carries its own
middleware explicitly — an isolated subagent does not inherit the
parent agent's middleware.

**Functions:**

- [**make_researcher_spec**](make_researcher_spec.md) – Build the researcher subagent spec.
- [**make_verifier_spec**](make_verifier_spec.md) – Build the verifier subagent spec.
