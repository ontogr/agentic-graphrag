---
title: agrag.agents.tools
sidebar_label: tools
---

# `agrag.agents.tools` \{#agrag-agents-tools}

Agent tools: thin wrappers calling SearchEngine with fixed Recipes.

Each tool is a LangChain-compatible callable that deepagents can register.
Tools are named for what the agent is trying to find out, not for the
retrieval method they use.

**Modules:**

- [**aggregate**](aggregate/index.md) – Deterministic arithmetic over numbers the agent has already gathered.
- [**search**](search/index.md) – Discovery tools: fixed-Recipe searches over SearchEngine.
- [**traversal**](traversal/index.md) – Entity-graph tools: resolve a named entity, then walk its relationships.

**Functions:**

- [**make_tools**](make_tools.md) – Build the agent's tool set over one SearchEngine and Ledger.
