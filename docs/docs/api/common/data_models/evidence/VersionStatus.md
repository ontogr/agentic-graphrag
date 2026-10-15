---
title: agrag.common.data_models.evidence.VersionStatus
sidebar_label: VersionStatus
---

# `agrag.common.data_models.evidence.VersionStatus` \{#agrag-common-data_models-evidence-VersionStatus}

Bases: <code>StrEnum</code>

Whether the fetched text is the current version of its document.

**Attributes:**

- [**CURRENT**](#agrag-common-data_models-evidence-VersionStatus-CURRENT) – The content hash equals the document's current content hash.
- [**SUPERSEDED**](#agrag-common-data_models-evidence-VersionStatus-SUPERSEDED) – The document has changed since this text was written. The
  text is still returned, and it is not discoverable.

## `CURRENT` \{#agrag-common-data_models-evidence-VersionStatus-CURRENT}

```python
CURRENT = 'current'
```

## `SUPERSEDED` \{#agrag-common-data_models-evidence-VersionStatus-SUPERSEDED}

```python
SUPERSEDED = 'superseded'
```
