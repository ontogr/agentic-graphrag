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

- [**AddResult**](add_result/AddResult.md) – Return type of Graph.add(). One summary per pipeline stage.
- [**CommunityDetectionReport**](community_detection_report/CommunityDetectionReport.md) – Report from Graph.detect_communities().
- [**ConsolidationReport**](consolidation_report/ConsolidationReport.md) – Report from Graph.consolidate().
- [**ReevaluationReport**](reevaluation_report/ReevaluationReport.md) – Report from Graph.reevaluate().
- [**UpdateResult**](update_result/UpdateResult.md) – Summary of an update or soft deletion.
