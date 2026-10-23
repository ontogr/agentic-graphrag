"""Shared tool contract for the evidence functions, MCP tools and agent tools.

The module holds only constants, annotated argument types and tool description
strings. Every surface that exposes an evidence tool imports its argument
bounds and description from here, so the three surfaces stay identical.
"""

from typing import Annotated

from pydantic import Field, ValidationError
from pydantic.v1.error_wrappers import ValidationError as V1ValidationError

from agrag.common.data_models.evidence import EvidenceSearchMode


DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50
DEFAULT_SUPPORT_LIMIT = 3
MAX_SUPPORT_LIMIT = 10
DEFAULT_THEME_LIMIT = 5
MAX_THEME_LIMIT = 10
DEFAULT_FETCH_MAX_CHARS = 4000
MAX_QUERY_CHARS = 1000
MAX_LABELS = 20
MAX_RELATION_TYPES = 20
MAX_DEPTH = 2
MAX_EXPLORE_BOUND = 200
DEFAULT_MAX_NODES = 25
DEFAULT_MAX_EDGES = 50
DEFAULT_NAV_LIMIT = 10
DEFAULT_NAV_MAX_CHARS = 12000
MAX_NAV_MAX_CHARS = 20000
MAX_EVIDENCE_IDS = 20


Query = Annotated[str, Field(min_length=1, max_length=MAX_QUERY_CHARS)]
SearchLimit = Annotated[int, Field(ge=1, le=MAX_SEARCH_LIMIT)]
SupportLimit = Annotated[int, Field(ge=1, le=MAX_SUPPORT_LIMIT)]
ThemeLimit = Annotated[int, Field(ge=1, le=MAX_THEME_LIMIT)]
Labels = Annotated[list[str] | None, Field(max_length=MAX_LABELS)]
RelationTypes = Annotated[list[str] | None, Field(max_length=MAX_RELATION_TYPES)]
EntityId = Annotated[str, Field(min_length=1, max_length=100)]
ExploreDepth = Annotated[int, Field(ge=1, le=MAX_DEPTH)]
ExploreBound = Annotated[int, Field(ge=1, le=MAX_EXPLORE_BOUND)]
EvidenceId = Annotated[str, Field(min_length=1, max_length=500)]
EvidenceIds = Annotated[list[str], Field(min_length=1, max_length=MAX_EVIDENCE_IDS)]
FetchMaxChars = Annotated[int | None, Field(ge=1)]
NavMaxChars = Annotated[int, Field(ge=1, le=MAX_NAV_MAX_CHARS)]
SearchMode = EvidenceSearchMode


SEARCH_EVIDENCE = (
    "Search the configured documents for passages that match a query, by "
    "keyword, by meaning, or both. Each hit carries an evidence id and a "
    "snippet. A score orders hits and is not a confidence. No hits does not "
    "prove that the documents lack the information. Use this tool for "
    "passages. Use entity_search when the question names a thing, and "
    "search_themes for broad questions that span many documents. Pass the "
    "evidence ids of the hits you use to fetch_evidence before citing them."
)
ENTITY_SEARCH = (
    "Find entities in the configured documents whose name or meaning matches "
    "a query, each with up to a few passages that mention it. A score orders "
    "hits and is not a confidence. An entity without passages is not stated "
    "by the current text. Use this tool when the question names a thing; use "
    "search_evidence for passages and search_themes for broad questions. "
    "Pass the evidence ids in a hit's support to fetch_evidence."
)
EXPLORE_RELATIONSHIPS = (
    "Explore the relations around one entity within fixed bounds, up to two "
    "steps from the start. The entity id comes from entity_search. A relation "
    "with passages is an assertion; a connection with no passage is a path, "
    "and a path is not a fact. Use this tool to learn how things connect; use "
    "search_evidence for passages. Pass the evidence ids of the assertions "
    "you use to fetch_evidence."
)
NAVIGATE_DOCUMENT_TREE = (
    "Read nearby passages of the same document version around one evidence "
    "id: the previous or next passage, child passages, the passages before "
    "and after a table row, or the parent and sibling sections. Use it to "
    "read around a hit from search_evidence. Passages outside the configured "
    "scope are never returned. Pass the evidence ids of the items you use to "
    "fetch_evidence."
)
SEARCH_THEMES = (
    "Find themes in the configured documents: clusters of related entities "
    "found by community detection, each with the passages that mention its "
    "member entities. A score orders themes and is not a confidence. "
    "Membership comes from the last community detection run; documents added "
    "after that run are absent, and hidden or out-of-scope passages are "
    "filtered out. Use this tool for broad questions that span many "
    "documents; use search_evidence for passages and entity_search when the "
    "question names a thing. Pass the evidence ids of the passages you use "
    "to fetch_evidence."
)
FETCH_EVIDENCE = (
    "Return the exact text behind evidence ids from search_evidence, "
    "entity_search, explore_relationships, navigate_document_tree or "
    "search_themes. Always fetch the ids you use before citing them. Ids "
    "outside the configured scope and missing ids both return unavailable. "
    "Complete fetches carry a citation reference; keep the evidence id for "
    "check_citations."
)
CHECK_CITATIONS = (
    "Check that the evidence ids an answer cites were fetched in this "
    "session, within the configured scope. A valid verdict shows "
    "traceability only; it does not show that the text supports the claim. "
    "not_fetched means the id was not fetched."
)


def validation_message(exc: ValidationError | V1ValidationError) -> str:
    """Return one repair line per argument error for a failed tool input."""
    lines = [
        f"{error['loc'][0] if error['loc'] else 'input'}: {error['msg']}"
        for error in exc.errors()
    ]
    return "Invalid arguments. " + " ".join(lines)
