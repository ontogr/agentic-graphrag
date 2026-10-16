---
title: agrag.memory.decisions.DecisionMemory
sidebar_label: DecisionMemory
---

# `agrag.memory.decisions.DecisionMemory` \{#agrag-memory-decisions-DecisionMemory}

```python
DecisionMemory(store:GraphStore, *, project_id:str, agent_id:str) -> None
```

Write and search durable decisions for one configured project.

**Functions:**

- [**continue_review_propagation**](#agrag-memory-decisions-DecisionMemory-continue_review_propagation) – Expand at most `limit` queued decisions by one dependency hop each.
- [**get_decision**](#agrag-memory-decisions-DecisionMemory-get_decision) – Read a decision only when it belongs to this project.
- [**list_conflicts**](#agrag-memory-decisions-DecisionMemory-list_conflicts) – List active same-choice decisions with different conclusions.
- [**list_decisions**](#agrag-memory-decisions-DecisionMemory-list_decisions) – List decisions for a task, including lifecycle history by default.
- [**list_review**](#agrag-memory-decisions-DecisionMemory-list_review) – List active decisions that need a look, within this project's bounds.
- [**list_support_history**](#agrag-memory-decisions-DecisionMemory-list_support_history) – Read exact historical support associations and who reviewed them.
- [**reaffirm_decision**](#agrag-memory-decisions-DecisionMemory-reaffirm_decision) – Confirm a decision still stands on the current version of its documents.
- [**record_decision**](#agrag-memory-decisions-DecisionMemory-record_decision) – Record a decision only when every support is valid and in scope.
- [**reject_decision**](#agrag-memory-decisions-DecisionMemory-reject_decision) – Mark a decision rejected without changing its recorded conclusion.
- [**resolve_supports**](#agrag-memory-decisions-DecisionMemory-resolve_supports) – Resolve typed supports in a caller-owned transaction.
- [**search_decisions**](#agrag-memory-decisions-DecisionMemory-search_decisions) – Find same-project decisions as precedents, with their task context.
- [**supersede_decision**](#agrag-memory-decisions-DecisionMemory-supersede_decision) – Record a same-choice replacement and preserve the old decision.

## `continue_review_propagation` \{#agrag-memory-decisions-DecisionMemory-continue_review_propagation}

```python
continue_review_propagation(*, limit:int = 100) -> int
```

Expand at most `limit` queued decisions by one dependency hop each.

## `get_decision` \{#agrag-memory-decisions-DecisionMemory-get_decision}

```python
get_decision(decision_id:UUID) -> DecisionLookup
```

Read a decision only when it belongs to this project.

## `list_conflicts` \{#agrag-memory-decisions-DecisionMemory-list_conflicts}

```python
list_conflicts() -> ConflictList
```

List active same-choice decisions with different conclusions.

## `list_decisions` \{#agrag-memory-decisions-DecisionMemory-list_decisions}

```python
list_decisions(task_name:str, *, include_history:bool = True) -> DecisionPageLookup
```

List decisions for a task, including lifecycle history by default.

## `list_review` \{#agrag-memory-decisions-DecisionMemory-list_review}

```python
list_review(*, task_name:str | None = None, limit:int = 20) -> DecisionReviewList
```

List active decisions that need a look, within this project's bounds.

A listed decision is flagged because a source or a decision it depends
on changed. Review means it needs a look, not that it is false. Use
`reaffirm_decision`, `supersede_decision` or `reject_decision` to
clear the flag.

**Parameters:**

- **task_name** (<code>str | None</code>) – Only list decisions of this task, or all tasks if None.
- **limit** (<code>int</code>) – The number of decisions to return, capped at the page limit.

**Returns:**

- <code>[DecisionReviewList](../../common/data_models/decision/DecisionReviewList.md)</code> – The decisions in the page, the total count, and whether more exist.

## `list_support_history` \{#agrag-memory-decisions-DecisionMemory-list_support_history}

```python
list_support_history(decision_id:UUID, *, after_ordinal:int = -1, limit:int = 20) -> SupportHistoryPage
```

Read exact historical support associations and who reviewed them.

## `reaffirm_decision` \{#agrag-memory-decisions-DecisionMemory-reaffirm_decision}

```python
reaffirm_decision(decision_id:UUID, evidence:Sequence[DocumentSupportInput], *, fetched_evidence:Sequence[FetchOutcome] = (), explanation:str = 'Reaffirmed after review.', request_id:str | None = None) -> ReaffirmDecisionResult
```

Confirm a decision still stands on the current version of its documents.

Review means the decision needs a look. It does not mean the decision
is false. Reaffirming records the caller as the reviewer, replaces the
decision's document supports with `evidence`, and clears the review
flag. It does not change the flags of dependent decisions.

Every document the decision cites must be fetched in its current
version, and `evidence` must cite exactly those documents. A cited
document that is removed, or whose current version was not fetched
with status `ok`, fails with `cannot_revalidate` and the decision
stays flagged. So does a decision that depends on another decision
still needing review.

**Parameters:**

- **decision_id** (<code>UUID</code>) – The id of the active decision to reaffirm.
- **evidence** (<code>Sequence\[[DocumentSupportInput](../../common/data_models/decision/DocumentSupportInput.md)\]</code>) – The new document supports, one or more per cited document.
- **fetched_evidence** (<code>Sequence\[[FetchOutcome](../../common/data_models/evidence/FetchOutcome.md)\]</code>) – Fetch outcomes from this session. They must cover
  the current version of each cited document.
- **explanation** (<code>str</code>) – The reason the reviewer accepts the current supports.
- **request_id** (<code>str | None</code>) – An optional key that makes a retry return the stored
  result of the first call.

**Returns:**

- <code>[ReaffirmDecisionResult](../../common/data_models/decision/ReaffirmDecisionResult.md)</code> – The reaffirmed decision, or a result with an error code.

## `record_decision` \{#agrag-memory-decisions-DecisionMemory-record_decision}

```python
record_decision(task_name:str, choice_key:str, conclusion:str, rationale:str, *, supports:Sequence[SupportInput], fetched_evidence:Sequence[FetchOutcome] = (), assumptions:Sequence[str] = (), open_questions:Sequence[str] = (), request_id:str | None = None) -> RecordDecisionResult
```

Record a decision only when every support is valid and in scope.

Document evidence must appear in `fetched_evidence` with status
`ok`. All checks and writes share one graph transaction.

## `reject_decision` \{#agrag-memory-decisions-DecisionMemory-reject_decision}

```python
reject_decision(decision_id:UUID, reason:str, *, request_id:str | None = None) -> RejectDecisionResult
```

Mark a decision rejected without changing its recorded conclusion.

## `resolve_supports` \{#agrag-memory-decisions-DecisionMemory-resolve_supports}

```python
resolve_supports(tx:GraphStoreTransaction, supports:Sequence[SupportInput], fetched:Sequence[FetchOutcome]) -> tuple[list[dict[str, Any]], bool]
```

Resolve typed supports in a caller-owned transaction.

Returns property maps and whether any observed source has changed.
Raises ValueError when a reference cannot be resolved or was not fetched.

## `search_decisions` \{#agrag-memory-decisions-DecisionMemory-search_decisions}

```python
search_decisions(query:str, *, task_name:str | None = None, limit:int = 20) -> list[DecisionHit]
```

Find same-project decisions as precedents, with their task context.

## `supersede_decision` \{#agrag-memory-decisions-DecisionMemory-supersede_decision}

```python
supersede_decision(decision_id:UUID, conclusion:str, rationale:str, *, explanation:str, supports:Sequence[SupportInput], fetched_evidence:Sequence[FetchOutcome] = (), assumptions:Sequence[str] = (), open_questions:Sequence[str] = (), request_id:str | None = None) -> RecordDecisionResult
```

Record a same-choice replacement and preserve the old decision.
