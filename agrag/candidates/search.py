"""Word search over pending and approved candidates."""

import re

from agrag.common.data_models.candidate import CandidateKind, CandidateRecord
from agrag.common.text import normalize_text
from agrag.cypher.candidate_search import search_candidates_query
from agrag.graphdb.base import GraphStore


async def search_candidates(
    graph_store: GraphStore,
    query: str,
    *,
    kind: CandidateKind | None = None,
    limit: int = 10,
) -> list[CandidateRecord]:
    """Find candidates whose label or text holds any word of the query.

    Search is lexical because candidates have no embedding. Rejected
    candidates are excluded, and words shorter than three characters are
    ignored.

    Args:
        graph_store: The store that holds the candidates.
        query: The words to look for.
        kind: Only this kind. None searches every kind.
        limit: The most candidates to return.

    Returns:
        Candidates ranked by matching-word count, then frequency.
    """
    terms = sorted(
        {word for word in re.findall(r"\w+", normalize_text(query)) if len(word) > 2}
    )
    if not terms or limit < 1:
        return []
    rows = await graph_store.execute_read(
        search_candidates_query(), {"terms": terms, "kind": kind, "limit": limit}
    )
    return [CandidateRecord.model_validate(row["candidate"]) for row in rows]
