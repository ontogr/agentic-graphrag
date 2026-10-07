---
title: agrag.eval.CitationSentenceRow
sidebar_label: CitationSentenceRow
---

# `agrag.eval.CitationSentenceRow` \{#agrag-eval-CitationSentenceRow}

Bases: <code>TypedDict</code>

One cited sentence and its support verdict, for the report.

**Attributes:**

- [**text**](#agrag-eval-CitationSentenceRow-text) (<code>str</code>) – The sentence with its citation keys removed.
- [**keys**](#agrag-eval-CitationSentenceRow-keys) (<code>list\[str\]</code>) – The keys the sentence cites, including bracketed keys the run
  never assigned. Empty only when the sentence cites no key-shaped
  token at all.
- [**fabricated**](#agrag-eval-CitationSentenceRow-fabricated) (<code>bool</code>) – Whether the sentence cites a key the run never assigned.
- [**supported**](#agrag-eval-CitationSentenceRow-supported) (<code>bool</code>) – Whether the cited evidence supports the sentence.
- [**reason**](#agrag-eval-CitationSentenceRow-reason) (<code>str</code>) – The support judge's reason, or why no judge call happened.

## `fabricated` \{#agrag-eval-CitationSentenceRow-fabricated}

```python
fabricated: bool
```

## `keys` \{#agrag-eval-CitationSentenceRow-keys}

```python
keys: list[str]
```

## `reason` \{#agrag-eval-CitationSentenceRow-reason}

```python
reason: str
```

## `supported` \{#agrag-eval-CitationSentenceRow-supported}

```python
supported: bool
```

## `text` \{#agrag-eval-CitationSentenceRow-text}

```python
text: str
```
