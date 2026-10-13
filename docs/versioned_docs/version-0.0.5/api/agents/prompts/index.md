---
title: agrag.agents.prompts
sidebar_label: prompts
---

# `agrag.agents.prompts` \{#agrag-agents-prompts}

Agent prompt templates for planner, researcher, verifier, and fallback.

Each constant carries at most one `{placeholder}` token, substituted
with `str.replace()` at agent-build time — never `str.format()`,
which would raise on any other brace the text picks up over time.

**Attributes:**

- [**PLANNER_SYSTEM**](PLANNER_SYSTEM.md) –
- [**RESEARCHER_SYSTEM**](RESEARCHER_SYSTEM.md) –
- [**SIMPLE_ANSWER_SYSTEM**](SIMPLE_ANSWER_SYSTEM.md) –
- [**VERIFIER_SYSTEM**](VERIFIER_SYSTEM.md) –
