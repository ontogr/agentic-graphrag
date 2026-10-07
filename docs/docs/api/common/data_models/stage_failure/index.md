---
title: agrag.common.data_models.stage_failure
sidebar_label: stage_failure
---

# `agrag.common.data_models.stage_failure` \{#agrag-common-data_models-stage_failure}

Per-stage failure record and its per-call cap.

**Classes:**

- [**CappedFailures**](CappedFailures.md) – A capped failure list plus the true count it was built from.
- [**StageFailure**](StageFailure.md) – One item failure within a pipeline stage.

**Functions:**

- [**cap_failures**](cap_failures.md) – Return failures capped per stage, with the untruncated true count.

**Attributes:**

- [**MAX_FAILURES_PER_STAGE**](MAX_FAILURES_PER_STAGE.md) –
- [**logger**](logger.md) –
