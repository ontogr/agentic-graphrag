---
title: agrag.agents.model
sidebar_label: model
---

# `agrag.agents.model` \{#agrag-agents-model}

Translate LLMClientConfig into the matching LangChain chat model.

**Classes:**

- [**UnsupportedAgentProviderError**](UnsupportedAgentProviderError.md) – Raised when a provider has no agent-side mapping yet.

**Functions:**

- [**build_chat_model**](build_chat_model.md) – Translate one LLMClientConfig into a LangChain chat model.
- [**build_model_middleware**](build_model_middleware.md) – Build agent middleware composing multiple clients per strategy.
