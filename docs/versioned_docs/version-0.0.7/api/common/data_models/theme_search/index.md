---
title: agrag.common.data_models.theme_search
sidebar_label: theme_search
---

# `agrag.common.data_models.theme_search` \{#agrag-common-data_models-theme_search}

Models for theme search over detected communities.

A theme is a community of related entities found by the last community
detection run. A hit carries the community id, the passages in the caller's
scope that mention its member entities, and the names of those members.
Community report text (title, summary, findings) is never returned: community
nodes carry no document scope, so their text may reflect documents outside the
caller's scope.

**Classes:**

- [**ThemeHit**](ThemeHit.md) – One theme found by theme search.
- [**ThemeResult**](ThemeResult.md) – The result of one theme search call.
