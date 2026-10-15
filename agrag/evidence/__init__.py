"""Evidence discovery, exact fetch and citation checks over Document text.

The functions take a graph store and enforce the caller's document scope inside
their queries. Evidence ids name passage text of one version of a document.
"""

from agrag.evidence.citation import check_citations
from agrag.evidence.discover import discover
from agrag.evidence.fetch import fetch
from agrag.evidence.source_status import source_status


__all__ = ["check_citations", "discover", "fetch", "source_status"]
