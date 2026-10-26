---
title: agrag.agents.harness.ensure_harness_profile
sidebar_label: ensure_harness_profile
---

# `agrag.agents.harness.ensure_harness_profile` \{#agrag-agents-harness-ensure_harness_profile}

```python
ensure_harness_profile(provider:str) -> None
```

Register the harness profile for provider, once per process.

**Parameters:**

- **provider** (<code>str</code>) – The provider key DeepAgents resolves profiles by,
  either a provider string such as `"anthropic"` or an
  exact `"provider:model"` string.
