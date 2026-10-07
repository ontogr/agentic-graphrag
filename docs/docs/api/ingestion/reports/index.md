---
title: agrag.ingestion.reports
sidebar_label: reports
---

# `agrag.ingestion.reports` \{#agrag-ingestion-reports}

Reports returned by Graph pipeline operations.

One class per module under this package; this init re-exports them so
`from agrag.ingestion.reports import AddResult` keeps working.

**Modules:**

- [**add_result**](add_result/index.md) – Graph.add()'s result type.
- [**community_detection_report**](community_detection_report/index.md) – Graph.detect_communities()'s result type.
- [**consolidation_report**](consolidation_report/index.md) – Graph.consolidate()'s result type.
- [**reevaluation_report**](reevaluation_report/index.md) – Graph.reevaluate()'s result type.
- [**update_result**](update_result/index.md) – Result returned by document lifecycle operations.

**Classes:**

- [**AddResult**](AddResult.md) – Graph.add()'s return type — one summary per pipeline stage.
- [**CommunityDetectionReport**](CommunityDetectionReport.md) – Report from Graph.detect_communities().
- [**ConsolidationReport**](ConsolidationReport.md) – Report from Graph.consolidate().
- [**ReevaluationReport**](ReevaluationReport.md) – Report from Graph.reevaluate().
- [**UpdateResult**](UpdateResult.md) – Summary of an update or soft deletion.
