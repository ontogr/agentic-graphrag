"""Index descriptions that a graph store reports to retrieval and ingestion."""

from dataclasses import dataclass, field
from typing import Any


INDEX_STATE_ONLINE = "ONLINE"


@dataclass(frozen=True)
class IndexInfo:
    """One search or lookup index in the graph database.

    Attributes:
        name: The index name. Backends that do not name indexes derive the same
            deterministic name that ``vector_index_name`` and
            ``fulltext_index_name`` build.
        state: ``ONLINE`` when queries can use the index. Any other value means
            the index is still being built or has failed.
        population_percent: How much of the index is built, from 0 to 100. None
            when the backend does not report progress.
        type: ``VECTOR``, ``FULLTEXT``, or another backend index type.
        labels: The node labels or relationship types the index covers.
        properties: The indexed property names.
        dimensions: The embedding size of a ``VECTOR`` index, otherwise None.
    """

    name: str
    state: str
    population_percent: float | None
    type: str
    labels: list[str]
    properties: list[str]
    dimensions: int | None = None


@dataclass(frozen=True)
class SearchCall:
    """A Cypher fragment that searches one index, plus the parameters it needs.

    The fragment starts with ``CALL`` and ends after ``YIELD node, score``. It
    expects ``$k`` (candidates to read) and either ``$fulltext_terms`` or
    ``$vector``. ``score`` is higher for a closer match whatever the backend's
    own scale is.

    Attributes:
        text: The Cypher fragment.
        params: Parameters the fragment needs beyond the caller's own.
    """

    text: str
    params: dict[str, Any] = field(default_factory=dict)
