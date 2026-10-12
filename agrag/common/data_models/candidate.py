"""Candidate items rejected by the extraction schema."""

import hashlib
import re
import unicodedata
from typing import Literal
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, Field, model_validator


CANDIDATE_LABEL = "Candidate"
EVIDENCED_BY = "EVIDENCED_BY"
SOURCE = "SOURCE"
TARGET = "TARGET"
CANDIDATE_EDGE_TYPES = frozenset({EVIDENCED_BY, SOURCE, TARGET})

CandidateKind = Literal["entity", "relation", "property"]
CandidateReason = Literal[
    "off_pattern",
    "below_relation_cut",
    "unresolved_endpoint",
    "entity_band",
    "property",
]
CandidateState = Literal["pending", "approved", "rejected"]
_MAX_TEXT_CHARS = 200
_LEADING_ARTICLE = re.compile(r"^\s*(?:the|an|a)\s+(?=\S)")
_INNER_DOT = re.compile(r"(?<=\w)\.(?=\w)")
_NON_WORD_RUN = re.compile(r"[\W_]+")


def normalize_candidate_text(text: str) -> str:
    """Fold case, accents, punctuation and a leading English article."""
    decomposed = unicodedata.normalize("NFKD", text)
    unmarked = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    folded = _LEADING_ARTICLE.sub("", unmarked.casefold(), count=1)
    words = _NON_WORD_RUN.sub(" ", _INNER_DOT.sub("", folded)).strip()
    if len(words) > _MAX_TEXT_CHARS:
        digest = hashlib.sha256(words.encode()).hexdigest()[:16]
        return f"{words[:_MAX_TEXT_CHARS]}~{digest}"
    return words


def candidate_key(
    kind: CandidateKind, label: str, subject: str | tuple[str, str]
) -> str:
    """Build a stable deduplication key for candidate content."""
    label_part = normalize_candidate_text(label)
    parts: tuple[str, ...]
    if isinstance(subject, tuple):
        parts = subject
    else:
        parts = (normalize_candidate_text(subject),)
    return f"{kind}|{label_part}|{'|'.join(parts)}"


def _end_reference(entity_id: UUID | None, text: str | None) -> str:
    if entity_id is not None:
        return str(entity_id)
    return f"~{normalize_candidate_text(text or '')}"


class CandidateRecord(BaseModel):
    """One rejected extraction item, stored outside the entity graph.

    Each job uses a new node id. The key groups sightings across jobs without
    changing a committed node's count. Entity and property candidates need
    text. Relation endpoints need an entity id or unresolved text.

    Attributes:
        id: Per-job node id, random unless supplied by the caller.
        kind: Entity, relation or property candidate.
        label: Proposed entity type, relation type or property name.
        text: Entity surface text or property value. Empty for relations.
        source_text: Unresolved source endpoint or property holder text.
        target_text: Unresolved target endpoint text.
        confidence: Extractor score from 0 to 1. Use 0 for an unscored item.
        reason: Why the extractor rejected the item.
        chunk_id: Evidence chunk id.
        source_entity_id: Source endpoint or property holder, when resolved.
        target_entity_id: Target endpoint, when resolved.
        source_label: Source endpoint or property holder type, when known.
        target_label: Target endpoint type, when known.
        state: Review state, initially pending.
        count: Sightings represented by this node, fixed on creation.
        schema_fingerprint: Schema used to extract the item, empty if unknown.
    """

    id: UUID = Field(default_factory=uuid4)
    kind: CandidateKind
    label: str = Field(min_length=1)
    text: str = ""
    source_text: str | None = None
    target_text: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: CandidateReason
    chunk_id: UUID
    source_entity_id: UUID | None = None
    target_entity_id: UUID | None = None
    source_label: str | None = None
    target_label: str | None = None
    state: CandidateState = "pending"
    count: int = Field(default=1, ge=1)
    schema_fingerprint: str = ""

    @property
    def key(self) -> str:
        """Return the stable deduplication key for this record."""
        if self.kind == "relation":
            return candidate_key(
                "relation",
                self.label,
                (
                    _end_reference(self.source_entity_id, self.source_text),
                    _end_reference(self.target_entity_id, self.target_text),
                ),
            )
        if self.kind == "property":
            return candidate_key(
                "property",
                self.label,
                (
                    _end_reference(self.source_entity_id, self.source_text),
                    normalize_candidate_text(self.text),
                ),
            )
        return candidate_key("entity", self.label, self.text)

    @property
    def evidence_edge_id(self) -> UUID:
        """Return the deterministic evidence edge id."""
        return uuid5(self.id, f"{EVIDENCED_BY}:{self.chunk_id}")

    @property
    def source_edge_id(self) -> UUID | None:
        """Return the deterministic source edge id when its endpoint exists."""
        if self.source_entity_id is None:
            return None
        return uuid5(self.id, f"{SOURCE}:{self.source_entity_id}")

    @property
    def target_edge_id(self) -> UUID | None:
        """Return the deterministic target edge id when its endpoint exists."""
        if self.target_entity_id is None:
            return None
        return uuid5(self.id, f"{TARGET}:{self.target_entity_id}")

    @model_validator(mode="after")
    def _check_shape(self) -> "CandidateRecord":
        """Require the text and endpoints appropriate to each candidate kind."""
        if self.kind in ("entity", "property") and not normalize_candidate_text(
            self.text
        ):
            raise ValueError(f"a {self.kind} candidate needs text")
        if (
            self.kind == "property"
            and self.source_entity_id is None
            and not (normalize_candidate_text(self.source_text or ""))
        ):
            raise ValueError(
                "a property candidate needs source_entity_id or source_text"
            )
        if self.kind == "relation":
            for side, entity_id, text in (
                ("source", self.source_entity_id, self.source_text),
                ("target", self.target_entity_id, self.target_text),
            ):
                if entity_id is None and not normalize_candidate_text(text or ""):
                    raise ValueError(f"a relation candidate needs {side} id or text")
        return self
