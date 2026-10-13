---
title: agrag.common.data_models.candidate_review.states_that_reach
sidebar_label: states_that_reach
---

# `agrag.common.data_models.candidate_review.states_that_reach` \{#agrag-common-data_models-candidate_review-states_that_reach}

```python
states_that_reach(target:CandidateState) -> list[CandidateState]
```

List source states from which a candidate can enter `target`.

**Parameters:**

- **target** (<code>[CandidateState](../candidate/CandidateState.md)</code>) – State to enter.

**Returns:**

- <code>list\[[CandidateState](../candidate/CandidateState.md)\]</code> – Allowed source states in alphabetical order.
