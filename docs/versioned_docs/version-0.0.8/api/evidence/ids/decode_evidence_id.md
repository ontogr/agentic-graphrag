---
title: agrag.evidence.ids.decode_evidence_id
sidebar_label: decode_evidence_id
---

# `agrag.evidence.ids.decode_evidence_id` \{#agrag-evidence-ids-decode_evidence_id}

```python
decode_evidence_id(evidence_id:str) -> EvidenceReference
```

Return the reference an evidence id names.

**Parameters:**

- **evidence_id** (<code>str</code>) – A string produced by `encode_evidence_id`.

**Returns:**

- <code>[EvidenceReference](../../common/data_models/evidence/EvidenceReference.md)</code> – The decoded reference. Its content hash is the 16-character prefix.

**Raises:**

- <code>[MalformedEvidenceIdError](MalformedEvidenceIdError.md)</code> – The string is not a canonical evidence id, or it
  names a range that is empty or reversed.
