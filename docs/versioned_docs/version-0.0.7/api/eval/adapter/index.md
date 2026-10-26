---
title: agrag.eval.adapter
sidebar_label: adapter
---

# `agrag.eval.adapter` \{#agrag-eval-adapter}

Adapters that let plain scoring functions report through DeepEval.

**Classes:**

- [**ScoreMetric**](ScoreMetric.md) – A DeepEval metric backed by a plain scoring function.
- [**ScoreResult**](ScoreResult.md) – The outcome of one scoring function call.

**Functions:**

- [**parse_json_case**](parse_json_case.md) – Read the `(actual, expected)` models back from a JSON test case.
- [**to_json_case**](to_json_case.md) – Build a test case that carries structured data as JSON.

**Attributes:**

- [**ModelT**](ModelT.md) –
