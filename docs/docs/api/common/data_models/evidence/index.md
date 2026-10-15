---
title: agrag.common.data_models.evidence
sidebar_label: evidence
---

# `agrag.common.data_models.evidence` \{#agrag-common-data_models-evidence}

Models for evidence references, discovery results, fetch outcomes and citations.

Evidence is passage text from a Document, named by an evidence id. The models
here are the values that the evidence operations exchange with callers.

**Classes:**

- [**CitationCheck**](CitationCheck.md) – The verdict for one cited evidence id.
- [**CitationVerdict**](CitationVerdict.md) – Whether a citation traces to evidence the caller fetched.
- [**DiscoveryHit**](DiscoveryHit.md) – One visible passage found by discovery.
- [**DiscoveryLeg**](DiscoveryLeg.md) – One search leg that can find a passage.
- [**DiscoveryMode**](DiscoveryMode.md) – Which search legs discovery runs.
- [**DiscoveryResult**](DiscoveryResult.md) – The result of one discovery call.
- [**DiscoveryStatus**](DiscoveryStatus.md) – The overall outcome of a discovery call.
- [**EvidenceKind**](EvidenceKind.md) – The two forms of evidence reference.
- [**EvidenceLocation**](EvidenceLocation.md) – Where a passage sits in its source.
- [**EvidenceReference**](EvidenceReference.md) – A stable pointer to passage text of one version of a document.
- [**FetchOutcome**](FetchOutcome.md) – The result of fetching one evidence id.
- [**FetchStatus**](FetchStatus.md) – The outcome of fetching one evidence id.
- [**IndexState**](IndexState.md) – Whether the search indexes a mode needs are ready.
- [**LegFailure**](LegFailure.md) – A search leg that failed during discovery.
- [**SourceIndexStatus**](SourceIndexStatus.md) – The state and population progress of one search index.
- [**SourceState**](SourceState.md) – The lifecycle state of one document source.
- [**SourceStatus**](SourceStatus.md) – The committed version, active job and index state for one source.
- [**VersionStatus**](VersionStatus.md) – Whether the fetched text is the current version of its document.

**Attributes:**

- [**CONTENT_HASH_PREFIX_LENGTH**](CONTENT_HASH_PREFIX_LENGTH.md) –
