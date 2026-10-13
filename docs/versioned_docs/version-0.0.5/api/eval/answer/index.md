---
title: agrag.eval.answer
sidebar_label: answer
---

# `agrag.eval.answer` \{#agrag-eval-answer}

Answer-quality metrics for agrag, scored from questions and reference answers.

`answer_case` turns one agent run into a DeepEval test case. The four factories
build DeepEval metrics that run the judge once. `CitationAccuracyMetric` checks
each cited sentence against the evidence its citation keys point to.

All metrics judge against the evidence text the agent saw, as `Ledger.render`
shows it. A chunk shows in full, whatever its size.

**Classes:**

- [**CitationAccuracyMetric**](CitationAccuracyMetric.md) – Score whether each cited sentence follows from the evidence it cites.
- [**CitationScoreBreakdown**](CitationScoreBreakdown.md) – Available precision, recall, and sentence-count fields for one score.
- [**CitationSentenceRow**](CitationSentenceRow.md) – One cited sentence and its support verdict, for the report.

**Functions:**

- [**answer_case**](answer_case.md) – Build the test case that every answer-quality metric scores.
- [**context_precision**](context_precision.md) – Build the metric for useful evidence ranked before noise.
- [**context_recall**](context_recall.md) – Build the metric for reference facts that the evidence covers.
- [**correctness**](correctness.md) – Build the answer correctness metric against the reference.
- [**faithfulness**](faithfulness.md) – Build the metric for claims that the evidence the agent saw does not contradict.
- [**final_answer**](final_answer.md) – Return the text of the last assistant message in an agent run.

**Attributes:**

- [**ABSTENTION**](ABSTENTION.md) –
