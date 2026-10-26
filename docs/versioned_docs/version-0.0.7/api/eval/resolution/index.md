---
title: agrag.eval.resolution
sidebar_label: resolution
---

# `agrag.eval.resolution` \{#agrag-eval-resolution}

Resolution quality: B-cubed and pairwise scores of mention clusters.

`run_resolver` sends mention strings through a `Resolver` and returns the
clusters it forms. `cluster_quality_metric` compares those clusters with gold
clusters. The score is B-cubed F1. The breakdown also holds B-cubed precision
and recall and pairwise precision, recall and F1. The counting is
`er-evaluation`'s.

Both sides list mentions by index. A mention that is in no cluster is a cluster
of one, so a gold set can list only its multi-mention clusters.

**Classes:**

- [**ClusterAssignment**](ClusterAssignment.md) – A grouping of mentions, listed by position in the mention list.

**Functions:**

- [**cluster_quality_metric**](cluster_quality_metric.md) – Build a metric for cluster quality on one test case.
- [**resolution_case**](resolution_case.md) – Build a test case that holds predicted and gold clusters.
- [**run_resolver**](run_resolver.md) – Resolve mention strings and return the clusters the resolver forms.
- [**run_resolver_detailed**](run_resolver_detailed.md) – Resolve mention strings and return the clusters plus raw evidence.
