"""Models for bounded navigation around one evidence passage.

A navigation call starts from an evidence id and returns neighboring passages
of the same document version. The models here are the values that the call
exchanges with callers.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from agrag.common.data_models.evidence import EvidenceLocation, VersionStatus


class NavigationRelation(StrEnum):
    """The neighbor relation a navigation call follows.

    Attributes:
        PARENT: The section or sections that hold the passage.
        CHILDREN: The other passages under the same parent node.
        SIBLINGS: The other sections under the same parent section.
        PREVIOUS: The passage before this one in reading order.
        NEXT: The passage after this one in reading order.
        TABLE_CONTEXT: The row passages before and after a table passage, with
            the table itself.
    """

    PARENT = "parent"
    CHILDREN = "children"
    SIBLINGS = "siblings"
    PREVIOUS = "previous"
    NEXT = "next"
    TABLE_CONTEXT = "table_context"


class NavigationStatus(StrEnum):
    """The outcome of a navigation call.

    Attributes:
        OK: At least one item is returned.
        NO_MATCH: The passage exists, but the relation has no items for it.
        UNAVAILABLE: The id names no evidence this caller may read. Missing ids
            and ids outside the scope give this same outcome.
        MALFORMED: The id does not decode.
        FAILED: The store failed while reading the neighbors.
    """

    OK = "ok"
    NO_MATCH = "no_match"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    FAILED = "failed"


class TruncationReason(StrEnum):
    """The bound that cut a navigation result.

    Attributes:
        LIMIT: More items existed than the item limit allowed.
        CHARS: The text budget ran out. The last item may be cut.
    """

    LIMIT = "limit"
    CHARS = "chars"


class NavigationItem(BaseModel):
    """One passage returned by a navigation call.

    Attributes:
        evidence_id: The evidence id of the passage. Pass it to fetch,
            check_citations or navigate_document_tree.
        document_key: The key of the document the passage belongs to.
        heading_path: The headings above the passage, from the outermost down.
        kind: ``"text"`` for running text and ``"table"`` for a table passage.
        text: The passage text, cut to the character budget of the call.
        text_truncated: True when the text was cut to fit the character budget.
        location: The offsets or pages of the passage.
    """

    evidence_id: str
    document_key: str
    heading_path: list[str] = Field(default_factory=list)
    kind: Literal["text", "table"]
    text: str
    text_truncated: bool = False
    location: EvidenceLocation


class NavigationResult(BaseModel):
    """The result of one navigation call.

    Attributes:
        status: The overall outcome.
        items: The passages, in the order of the relation.
        truncated: True when a bound cut the items or the text.
        truncation_reason: The bound that cut the result, when ``truncated``.
        version_status: Whether the version of the starting passage is current.
            None when no passage was resolved.
        multi_section: True when the starting passage covers more than one
            section, so ``parent`` returns one item per section.
        detail: A short message for a malformed or failed id. None otherwise.
    """

    status: NavigationStatus
    items: list[NavigationItem] = Field(default_factory=list)
    truncated: bool = False
    truncation_reason: TruncationReason | None = None
    version_status: VersionStatus | None = None
    multi_section: bool = False
    detail: str | None = None
