---
title: agrag.agents.harness
sidebar_label: harness
---

# `agrag.agents.harness` \{#agrag-agents-harness}

Process-global DeepAgents harness profile registration.

Registers, once per process and per provider, the profile that trims
DeepAgents' generic tool surface for this project's agent: the execute
tool is excluded and the general-purpose subagent is disabled. The
registration is a process-global side effect, so it is guarded against
re-registration.

**Functions:**

- [**ensure_harness_profile**](ensure_harness_profile.md) – Register the harness profile for provider, once per process.
- [**model_provider_key**](model_provider_key.md) – Return the DeepAgents provider key for a configured agent provider.
