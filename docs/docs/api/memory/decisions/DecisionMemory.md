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

- [**get_decision**](#agrag-memory-decisions-DecisionMemory-get_decision) – Read a decision only when it belongs to this project.
- [**list_conflicts**](#agrag-memory-decisions-DecisionMemory-list_conflicts) – List active same-choice decisions with different conclusions.
- [**list_decisions**](#agrag-memory-decisions-DecisionMemory-list_decisions) – List decisions for a task, including lifecycle history by default.
- [**record_decision**](#agrag-memory-decisions-DecisionMemory-record_decision) – Record a decision only when every support is valid and in scope.
- [**reject_decision**](#agrag-memory-decisions-DecisionMemory-reject_decision) – Mark a decision rejected without changing its recorded conclusion.
- [**search_decisions**](#agrag-memory-decisions-DecisionMemory-search_decisions) – Find same-project decisions as precedents, with their task context.
- [**supersede_decision**](#agrag-memory-decisions-DecisionMemory-supersede_decision) – Record a same-choice replacement and preserve the old decision.

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
