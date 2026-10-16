---
title: agrag.evidence.citation
sidebar_label: citation
---

# `agrag.evidence.citation` \{#agrag-evidence-citation}

Check that cited evidence ids trace to evidence the caller fetched.

The check confirms traceability only. A `valid` verdict means the citation names
text that was fetched in scope. It does not show that the text supports a claim.

**Classes:**

- [**ParsedCitations**](ParsedCitations.md) – Evidence ids and malformed citation-like tokens found in text.

**Functions:**

- [**check_citations**](check_citations.md) – Return one verdict for each cited evidence id, in the order given.
- [**parse_citations**](parse_citations.md) – Extract canonical evidence ids and malformed citation-like tokens.
