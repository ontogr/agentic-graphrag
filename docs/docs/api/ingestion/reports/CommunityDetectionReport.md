---
title: agrag.ingestion.reports.CommunityDetectionReport
sidebar_label: CommunityDetectionReport
---

# `agrag.ingestion.reports.CommunityDetectionReport` \{#agrag-ingestion-reports-CommunityDetectionReport}

Bases: <code>BaseModel</code>

Report from Graph.detect_communities().

**Attributes:**

- [**communities**](#agrag-ingestion-reports-CommunityDetectionReport-communities) (<code>list\[[Community](../../common/data_models/community/Community-ref.md)\]</code>) – The communities this call found, whether applied or not.
- [**applied**](#agrag-ingestion-reports-CommunityDetectionReport-applied) (<code>bool</code>) – Whether the communities were written.
- [**failures**](#agrag-ingestion-reports-CommunityDetectionReport-failures) (<code>list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Failures generating an applied community's LLM report or
  embedding its report text. A failed community still gets
  written, with a heuristic report or a missing embedding in
  place of the failed step. Always empty when apply is False.

## `applied` \{#agrag-ingestion-reports-CommunityDetectionReport-applied}

```python
applied: bool = False
```

## `communities` \{#agrag-ingestion-reports-CommunityDetectionReport-communities}

```python
communities: list[Community] = Field(default_factory=list)
```

## `failures` \{#agrag-ingestion-reports-CommunityDetectionReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```
