"""Evidence search, exact fetch, navigation, entity search and citation checks.

The functions take a graph store and enforce the caller's document scope inside
their queries. Evidence ids name passage text of one version of a document.
"""

from agrag.evidence.citation import check_citations
from agrag.evidence.entities import entity_search, explore_relationships
from agrag.evidence.fetch import fetch_evidence
from agrag.evidence.navigate import navigate_document_tree
from agrag.evidence.render import render_citations
from agrag.evidence.rerank import CrossEncoderReranker, Reranker
from agrag.evidence.search import search_evidence
from agrag.evidence.source_status import source_status
from agrag.evidence.themes import search_themes


__all__ = [
    "CrossEncoderReranker",
    "Reranker",
    "check_citations",
    "entity_search",
    "explore_relationships",
    "fetch_evidence",
    "navigate_document_tree",
    "render_citations",
    "search_evidence",
    "search_themes",
    "source_status",
]
