---
title: agrag.eval.verifier
sidebar_label: verifier
---

# `agrag.eval.verifier` \{#agrag-eval-verifier}

Verifier calibration: does the verifier give the right verdict?

Each item is a fixed `(question, sub-questions, findings)` input with a gold
verdict. The verdict and the gold label are both one of three values, so scoring
is an equality check and needs no judge. `verdict_report` gives per-class
precision, recall and F1, the macro F1 that gates, and a confusion matrix.

**Classes:**

- [**ClassScores**](ClassScores.md) – Precision, recall and F1 of one verdict class.
- [**VerdictItem**](VerdictItem.md) – One fixed verifier input with its gold verdict.
- [**VerdictReport**](VerdictReport.md) – Scores of predicted verdicts against gold verdicts.

**Functions:**

- [**run_verifier**](run_verifier.md) – Run the verifier over items and return one label per item.
- [**verdict_case**](verdict_case.md) – Build a test case with the predicted and the gold verdict.
- [**verdict_match_metric**](verdict_match_metric.md) – Build a metric that scores 1.0 when the verdict equals the gold verdict.
- [**verdict_report**](verdict_report.md) – Score predicted verdicts against gold verdicts.
