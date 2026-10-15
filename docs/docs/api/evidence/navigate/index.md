---
title: agrag.evidence.navigate
sidebar_label: navigate
---

# `agrag.evidence.navigate` \{#agrag-evidence-navigate}

Navigate from one evidence passage to its neighbors, within scope and bounds.

A navigation call starts from an evidence id and follows one relation to other
passages of the same document version. Structure edges and reading order decide
the neighbors. Every returned passage belongs to a document in the caller's
scope, and it is read in the version the starting id names, so a superseded id
keeps its own neighbors.

**Functions:**

- [**navigate**](navigate-ref.md) – Return the passages that one relation reaches from an evidence id.

**Attributes:**

- [**MAX_CHARS**](MAX_CHARS.md) –
- [**MAX_LIMIT**](MAX_LIMIT.md) –
