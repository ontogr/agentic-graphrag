---
title: agrag.common.data_models.candidate_review.ALLOWED_TRANSITIONS
sidebar_label: ALLOWED_TRANSITIONS
---

# `agrag.common.data_models.candidate_review.ALLOWED_TRANSITIONS` \{#agrag-common-data_models-candidate_review-ALLOWED_TRANSITIONS}

```python
ALLOWED_TRANSITIONS: dict[CandidateState, frozenset[CandidateState]] = {'pending': frozenset({'approved', 'rejected'}), 'approved': frozenset({'rejected'}), 'rejected': frozenset()}
```
