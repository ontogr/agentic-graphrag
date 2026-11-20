---
title: agrag.common.data_models.decision.Support
sidebar_label: Support
---

# `agrag.common.data_models.decision.Support` \{#agrag-common-data_models-decision-Support}

```python
Support = Annotated[DocumentSupport | EventSupport | DecisionSupport, Field(discriminator='kind')]
```
