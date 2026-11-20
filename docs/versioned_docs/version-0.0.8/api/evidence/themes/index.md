---
title: agrag.evidence.themes
sidebar_label: themes
---

# `agrag.evidence.themes` \{#agrag-evidence-themes}

Find themes: entity communities with the passages that mention their members.

A theme comes from the last community detection run, so its membership can be
stale. Membership that has since become invisible is filtered by the query, so
no hidden or out-of-scope passage can appear; documents added after the last
run are absent until the next run. Only passages and member names are returned,
never community report text, because a community node carries no document
scope.

**Functions:**

- [**search_themes**](search_themes.md) – Find up to `limit` themes whose member passages match a query.
