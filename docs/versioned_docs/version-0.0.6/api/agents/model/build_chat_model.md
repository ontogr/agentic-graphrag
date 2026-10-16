---
title: agrag.agents.model.build_chat_model
sidebar_label: build_chat_model
---

# `agrag.agents.model.build_chat_model` \{#agrag-agents-model-build_chat_model}

```python
build_chat_model(config:LLMClientConfig) -> Any
```

Translate one LLMClientConfig into a LangChain chat model.

Covers anthropic, openai, openai-generic (mapped to ChatOpenAI
with base_url set), and google-ai. The remaining LLMProvider
values are valid for BAML but have no agent-side mapping yet.

**Parameters:**

- **config** (<code>LLMClientConfig</code>) – The provider, model, api_key, and base_url to use.

**Returns:**

- <code>Any</code> – A constructed, ready-to-call BaseChatModel.

**Raises:**

- <code>[UnsupportedAgentProviderError](UnsupportedAgentProviderError.md)</code> – config.provider has no
  agent-side mapping.
