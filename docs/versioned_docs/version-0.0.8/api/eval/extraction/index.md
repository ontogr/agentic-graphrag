---
title: agrag.eval.extraction
sidebar_label: extraction
---

# `agrag.eval.extraction` \{#agrag-eval-extraction}

Extraction quality: entity and relation-triple F1 against gold annotations.

A gold annotation for one chunk is a hand-written `ExtractionResult`. Scoring
has two steps. First, each predicted entity is aligned to a gold entity of the
same label. Second, each predicted relation is mapped through that alignment to
gold entity indices and compared as a `(source, label, target)` triple. Exact
alignment needs the same character span. Relaxed alignment needs an overlap
(intersection over union) of at least 0.5. Both are one to one: when several
predictions overlap gold entities, alignment maximizes valid pairs and then
total overlap. Unaligned predictions count as false positives.

Every case reports exact and relaxed results. The exact score gates. A large gap
between the two shows a span boundary problem, not a missed entity. The
counting is scikit-learn's `precision_recall_fscore_support`. Use
`micro_scores` for the dataset score, because a mean of per-chunk scores
weights a short chunk the same as a long one.

**Classes:**

- [**EntityBreakdown**](EntityBreakdown.md) – The `score_breakdown` of an entity quality metric for one case.
- [**ExtractionGold**](ExtractionGold.md) – One gold-annotated chunk of text.
- [**LabelCounts**](LabelCounts.md) – True positives, false positives and false negatives for one entity label.
- [**MicroScores**](MicroScores.md) – Dataset scores pooled over every item, for entities and relations.
- [**RelationBreakdown**](RelationBreakdown.md) – The `score_breakdown` of a relation quality metric for one case.
- [**Scores**](Scores.md) – Precision, recall and F1.

**Functions:**

- [**entity_quality_metric**](entity_quality_metric.md) – Build a metric for entity F1 on one test case.
- [**extraction_case**](extraction_case.md) – Build a test case that holds a predicted and a gold extraction.
- [**micro_scores**](micro_scores.md) – Pool measured entity and relation metrics into dataset scores.
- [**relation_quality_metric**](relation_quality_metric.md) – Build a metric for relation triple F1 on one test case.
- [**run_extractor**](run_extractor.md) – Run an extractor over gold items and build one test case per item.
