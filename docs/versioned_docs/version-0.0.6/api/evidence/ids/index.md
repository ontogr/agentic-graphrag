---
title: agrag.evidence.ids
sidebar_label: ids
---

# `agrag.evidence.ids` \{#agrag-evidence-ids}

Encode and decode evidence ids.

A span id has the form `ev1:s:<document_node_id>:<hash16>:<start>-<end>`, and a
chunk id has the form `ev1:c:<document_node_id>:<hash16>:<chunk_id>`. The
document node id and the chunk id are lowercase hyphenated UUIDs. The hash is the
first 16 lowercase hex characters of the content hash. The `ev1` prefix is the
format version. The decoder accepts only the exact canonical form, so two ids that
name the same reference are the same string.

**Classes:**

- [**MalformedEvidenceIdError**](MalformedEvidenceIdError.md) – An evidence id does not decode to a valid reference.

**Functions:**

- [**decode_evidence_id**](decode_evidence_id.md) – Return the reference an evidence id names.
- [**encode_evidence_id**](encode_evidence_id.md) – Return the evidence id of a reference.
