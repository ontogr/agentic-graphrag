---
title: agrag.common.validation
sidebar_label: validation
---

# `agrag.common.validation` \{#agrag-common-validation}

Validation helpers shared across storage backends.

**Functions:**

- [**require_encrypted_remote_connection**](require_encrypted_remote_connection.md) – Reject a plaintext connection to a non-local host carrying a credential.
- [**require_positive_batch_size**](require_positive_batch_size.md) – Check that a backend write's `batch_size` is usable.
- [**require_positive_max_concurrency**](require_positive_max_concurrency.md) – Check that a concurrency limit is positive.
- [**require_valid_alpha**](require_valid_alpha.md) – Check that a `hybrid_search` `alpha` is a valid dense/keyword weight.
- [**require_valid_search_limit**](require_valid_search_limit.md) – Check that a search/hybrid_search `limit` is usable across every backend.

**Attributes:**

- [**MAX_SEARCH_LIMIT**](MAX_SEARCH_LIMIT.md) –
