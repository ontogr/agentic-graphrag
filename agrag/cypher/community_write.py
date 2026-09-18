"""Cypher for the community-detection full-replace write path."""

from agrag.common.data_models.community import COMMUNITY_LABEL


def delete_communities_batch_query() -> str:
    """Build Cypher deleting up to $limit Community nodes and their edges.

    Called repeatedly by the caller (see
    agrag.ingestion.community.delete_all_communities) until no rows are
    deleted, rather than a single unbatched DETACH DELETE.

    Returns:
        Parameterized Cypher expecting $limit. Returns the count deleted.
    """
    return (
        f"MATCH (n:{COMMUNITY_LABEL}) WITH n LIMIT $limit "
        f"DETACH DELETE n RETURN count(n) AS deleted"
    )
