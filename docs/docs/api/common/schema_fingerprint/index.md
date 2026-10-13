---
title: agrag.common.schema_fingerprint
sidebar_label: schema_fingerprint
---

# `agrag.common.schema_fingerprint` \{#agrag-common-schema_fingerprint}

Fingerprints of a schema and of the extraction setup that ran against it.

`schema_fingerprint` covers structure. `extraction_fingerprint` covers what
the extractor reads besides structure: descriptions, the settings that change
its output, and the model name. `Graph` stores both on every document and
chunk it writes, and `update()` compares them.

**Classes:**

- [**RunRecord**](RunRecord.md) – What a document and its chunks record about the run that wrote them.

**Functions:**

- [**extraction_fingerprint**](extraction_fingerprint.md) – Return the hash of everything the extractor reads besides structure.
- [**run_record**](run_record.md) – Build the run record of a schema and a set of extraction settings.
- [**schema_fingerprint**](schema_fingerprint-ref.md) – Return the hash of the structure of a schema.
