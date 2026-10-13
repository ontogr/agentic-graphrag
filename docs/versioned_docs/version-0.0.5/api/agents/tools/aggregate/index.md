---
title: agrag.agents.tools.aggregate
sidebar_label: aggregate
---

# `agrag.agents.tools.aggregate` \{#agrag-agents-tools-aggregate}

Deterministic arithmetic over numbers the agent has already gathered.

The researcher reads counts and totals off prior tool results into its own
reasoning; this tool exists so the arithmetic on them is exact rather than
recalled from a language model's head. It queries nothing.

**Functions:**

- [**compute_over_evidence**](compute_over_evidence.md) – Compute a count, a sum, or a comparison over numbers you supply.
