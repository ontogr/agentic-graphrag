---
title: agrag.common.data_models.decision
sidebar_label: decision
---

# `agrag.common.data_models.decision` \{#agrag-common-data_models-decision}

Models for decision records: choices, their evidence supports and reads.

**Classes:**

- [**ConflictGroup**](ConflictGroup.md) – Active decisions of one choice key that disagree across tasks.
- [**ConflictList**](ConflictList.md) – Choice keys whose active decisions disagree across tasks.
- [**Decision**](Decision-ref.md) – One recorded decision of a task.
- [**DecisionHit**](DecisionHit.md) – A decision returned by precedent search.
- [**DecisionLookup**](DecisionLookup.md) – The result of reading one decision by id.
- [**DecisionPage**](DecisionPage.md) – A capped list of decisions with the total that matched.
- [**DecisionPageLookup**](DecisionPageLookup.md) – The result of listing a task's decisions by name.
- [**DecisionReviewList**](DecisionReviewList.md) – A bounded project-scoped page of decisions requiring review.
- [**DecisionStatus**](DecisionStatus.md) – Lifecycle state of a decision. Only active decisions are reused.
- [**DecisionSupport**](DecisionSupport.md) – A stored dependency on another decision.
- [**DecisionSupportInput**](DecisionSupportInput.md) – An active decision that this decision depends on.
- [**DocumentSupport**](DocumentSupport.md) – A stored document support, with the passage it names.
- [**DocumentSupportInput**](DocumentSupportInput.md) – A passage the caller fetched, named by its evidence id.
- [**EventSupport**](EventSupport.md) – A stored event support.
- [**EventSupportInput**](EventSupportInput.md) – An existing event of a task in the same project.
- [**ReaffirmDecisionResult**](ReaffirmDecisionResult.md) – The outcome of reaffirming a flagged decision.
- [**RecordDecisionResult**](RecordDecisionResult.md) – The outcome of recording a decision.
- [**RejectDecisionResult**](RejectDecisionResult.md) – The outcome of rejecting a decision.
- [**ReviewReason**](ReviewReason.md) – Why a decision needs review.
- [**ReviewState**](ReviewState.md) – Whether a decision's supports still hold.
- [**SupportHistoryPage**](SupportHistoryPage.md) – A bounded page of immutable support references and review transitions.
- [**SupportKind**](SupportKind.md) – Kind of a support that a decision cites.

**Attributes:**

- [**DECISION_LABEL**](DECISION_LABEL.md) –
- [**DEPENDS_ON**](DEPENDS_ON.md) –
- [**HAS_SUPPORT**](HAS_SUPPORT.md) –
- [**MADE**](MADE.md) –
- [**PRECEDENT_MARKER**](PRECEDENT_MARKER.md) –
- [**SUPERSEDES**](SUPERSEDES.md) –
- [**SUPPORT_LABEL**](SUPPORT_LABEL.md) –
- [**Support**](Support.md) –
- [**SupportInput**](SupportInput.md) –
