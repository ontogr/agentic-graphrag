"""Evidence discovery, exact fetch, navigation, entity search and citation checks.

The functions take a graph store and enforce the caller's document scope inside
their queries. Evidence ids name passage text of one version of a document.
"""

from agrag.evidence.citation import check_citations
from agrag.evidence.discover import discover
from agrag.evidence.entities import explore, find_entities
from agrag.evidence.fetch import fetch
from agrag.evidence.navigate import navigate


__all__ = [
    "check_citations",
    "discover",
    "explore",
    "fetch",
    "find_entities",
    "navigate",
]
