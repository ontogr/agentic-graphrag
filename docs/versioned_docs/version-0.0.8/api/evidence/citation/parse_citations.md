---
title: agrag.evidence.citation.parse_citations
sidebar_label: parse_citations
---

# `agrag.evidence.citation.parse_citations` \{#agrag-evidence-citation-parse_citations}

```python
parse_citations(text:str) -> ParsedCitations
```

Extract canonical evidence ids and malformed citation-like tokens.

IDs may appear alone or grouped in brackets with comma or semicolon
separators. Markdown links are ignored unless their label contains an
evidence-id-like token.
