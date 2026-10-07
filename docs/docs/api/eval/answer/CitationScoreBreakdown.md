---
title: agrag.eval.answer.CitationScoreBreakdown
sidebar_label: CitationScoreBreakdown
---

# `agrag.eval.answer.CitationScoreBreakdown` \{#agrag-eval-answer-CitationScoreBreakdown}

Bases: <code>TypedDict</code>

Available precision, recall, and sentence-count fields for one score.

All fields are optional because abstentions and uncited answers have partial
breakdowns.

**Attributes:**

- [**citation_precision**](#agrag-eval-answer-CitationScoreBreakdown-citation_precision) (<code>float</code>) – Fraction of cited sentences supported by evidence.
- [**citation_recall**](#agrag-eval-answer-CitationScoreBreakdown-citation_recall) (<code>float</code>) – Fraction of eligible sentences supported by evidence.
- [**cited_sentences**](#agrag-eval-answer-CitationScoreBreakdown-cited_sentences) (<code>int</code>) – Number of sentences with citations.
- [**supported_sentences**](#agrag-eval-answer-CitationScoreBreakdown-supported_sentences) (<code>int</code>) – Number of cited sentences supported by evidence.
- [**sentences**](#agrag-eval-answer-CitationScoreBreakdown-sentences) (<code>int</code>) – Number of eligible sentences in the answer.
- [**sentence_rows**](#agrag-eval-answer-CitationScoreBreakdown-sentence_rows) (<code>list\[[CitationSentenceRow](CitationSentenceRow.md)\]</code>) – One row per cited sentence with its keys and verdict.

## `citation_precision` \{#agrag-eval-answer-CitationScoreBreakdown-citation_precision}

```python
citation_precision: float
```

## `citation_recall` \{#agrag-eval-answer-CitationScoreBreakdown-citation_recall}

```python
citation_recall: float
```

## `cited_sentences` \{#agrag-eval-answer-CitationScoreBreakdown-cited_sentences}

```python
cited_sentences: int
```

## `sentence_rows` \{#agrag-eval-answer-CitationScoreBreakdown-sentence_rows}

```python
sentence_rows: list[CitationSentenceRow]
```

## `sentences` \{#agrag-eval-answer-CitationScoreBreakdown-sentences}

```python
sentences: int
```

## `supported_sentences` \{#agrag-eval-answer-CitationScoreBreakdown-supported_sentences}

```python
supported_sentences: int
```
