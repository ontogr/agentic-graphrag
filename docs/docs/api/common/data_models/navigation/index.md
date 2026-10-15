---
title: agrag.common.data_models.navigation
sidebar_label: navigation
---

# `agrag.common.data_models.navigation` \{#agrag-common-data_models-navigation}

Models for bounded navigation around one evidence passage.

A navigation call starts from an evidence id and returns neighboring passages
of the same document version. The models here are the values that the call
exchanges with callers.

**Classes:**

- [**NavigationItem**](NavigationItem.md) – One passage returned by a navigation call.
- [**NavigationRelation**](NavigationRelation.md) – The neighbor relation a navigation call follows.
- [**NavigationResult**](NavigationResult.md) – The result of one navigation call.
- [**NavigationStatus**](NavigationStatus.md) – The outcome of a navigation call.
- [**TruncationReason**](TruncationReason.md) – The bound that cut a navigation result.
