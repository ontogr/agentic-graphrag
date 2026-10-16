"""Models for evidence references, discovery results, fetch outcomes and citations.

Evidence is passage text from a Document, named by an evidence id. The models
here are the values that the evidence operations exchange with callers.
"""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


CONTENT_HASH_PREFIX_LENGTH = 16


class EvidenceKind(StrEnum):
    """The two forms of evidence reference.

    Attributes:
        SPAN: A character range of the document text of one version. The range
            is resolved from the chunks of that version.
        CHUNK: One chunk node, for chunks that carry no text offsets.
    """

    SPAN = "span"
    CHUNK = "chunk"


class EvidenceReference(BaseModel):
    """A stable pointer to passage text of one version of a document.

    The reference holds only the first 16 hex characters of the content hash,
    because that is what the evidence id carries. Fetch results give the full
    hash.

    Attributes:
        kind: Whether the reference names a span or a chunk.
        document_node_id: The id of the Document graph node.
        content_hash_prefix: The first 16 lowercase hex characters of the
            sha256 content hash of the version.
        char_start: The start offset of a span, in the document text.
        char_end: The exclusive end offset of a span, in the document text.
        chunk_id: The id of the chunk node of a chunk reference.
    """

    kind: EvidenceKind
    document_node_id: UUID
    content_hash_prefix: str = Field(pattern=r"^[0-9a-f]{16}$")
    char_start: int | None = None
    char_end: int | None = None
    chunk_id: UUID | None = None

    @model_validator(mode="after")
    def _check_fields_match_kind(self) -> "EvidenceReference":
        if self.kind is EvidenceKind.SPAN:
            if self.char_start is None or self.char_end is None:
                raise ValueError("a span reference needs char_start and char_end")
            if not 0 <= self.char_start < self.char_end:
                raise ValueError("a span needs 0 <= char_start < char_end")
            if self.chunk_id is not None:
                raise ValueError("a span reference does not carry a chunk_id")
        else:
            if self.chunk_id is None:
                raise ValueError("a chunk reference needs a chunk_id")
            if self.char_start is not None or self.char_end is not None:
                raise ValueError("a chunk reference does not carry offsets")
        return self


class EvidenceLocation(BaseModel):
    """Where a passage sits in its source.

    Attributes:
        char_start: The start offset of the passage text, or None for a passage
            with page provenance.
        char_end: The exclusive end offset, or None for a passage with page
            provenance.
        page_numbers: The pages of a passage with page provenance. Empty for a
            text passage.
    """

    char_start: int | None = None
    char_end: int | None = None
    page_numbers: list[int] = Field(default_factory=list)


class DiscoveryMode(StrEnum):
    """Which search legs discovery runs.

    Attributes:
        LEXICAL: Full-text search over chunk text.
        SEMANTIC: Vector search over chunk embeddings.
        HYBRID: Both legs, fused with reciprocal rank fusion.
    """

    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class DiscoveryLeg(StrEnum):
    """One search leg that can find a passage."""

    LEXICAL = "lexical"
    SEMANTIC = "semantic"


class DiscoveryStatus(StrEnum):
    """The overall outcome of a discovery call.

    Attributes:
        OK: Every leg ran and returned hits.
        PARTIAL: At least one leg failed, and the other leg returned hits. Read
            ``DiscoveryResult.failures`` before treating the list as complete.
        NO_MATCH: Every leg ran and no visible passage matched.
        EMPTY_SCOPE: The scope named no documents, so nothing was searched.
        INDEX_NOT_READY: A search index the mode needs is missing or not ONLINE.
        FAILED: Every leg that ran failed.
    """

    OK = "ok"
    PARTIAL = "partial"
    NO_MATCH = "no_match"
    EMPTY_SCOPE = "empty_scope"
    INDEX_NOT_READY = "index_not_ready"
    FAILED = "failed"


class IndexState(StrEnum):
    """Whether the search indexes a mode needs are ready.

    Attributes:
        READY: Every needed index exists and is ONLINE.
        NOT_READY: At least one needed index is missing or not ONLINE.
    """

    READY = "ready"
    NOT_READY = "not_ready"


class SourceState(StrEnum):
    """The lifecycle state of one document source."""

    CURRENT = "current"
    PENDING = "pending"
    FAILED = "failed"
    DELETED = "deleted"
    UNKNOWN = "unknown"


class SourceIndexStatus(BaseModel):
    """The state and population progress of one search index.

    Attributes:
        name: Database index name.
        state: Database state such as ``ONLINE``, ``POPULATING``, or ``FAILED``.
        population_percent: Population progress, or None when unavailable.
    """

    name: str
    state: str
    population_percent: float | None = None


class SourceStatus(BaseModel):
    """The committed version, active job and index state for one source.

    Attributes:
        document_key: Stable source key requested by the caller.
        state: Lifecycle state derived from committed rows and the latest job.
        content_hash: Hash of the committed current version, if any.
        activation_seq: Sequence number of the latest committed activation.
        version_id: Version id on the current open ``HAS_PART`` edges.
        job_id: Id of the latest incomplete cutover job.
        job_status: Lifecycle status of that job.
        lease_expires_at: Lease expiry timestamp rendered as text.
        job_age_seconds: Age of the latest incomplete job.
        job_error: Stored job error or expired-lease reason.
        indexes: Full-text and vector index states used by discovery.
    """

    document_key: str
    state: SourceState
    content_hash: str | None = None
    activation_seq: int | None = None
    version_id: str | None = None
    job_id: str | None = None
    job_status: str | None = None
    lease_expires_at: str | None = None
    job_age_seconds: float | None = None
    job_error: str | None = None
    indexes: list[SourceIndexStatus] = Field(default_factory=list)


class DiscoveryHit(BaseModel):
    """One visible passage found by discovery.

    Attributes:
        evidence_id: The evidence id of the passage. Pass it to fetch and
            check_citations.
        document_key: The key of the document the passage belongs to.
        title: The title of that document.
        content_hash: The full sha256 content hash of the current version.
        location: The offsets or pages of the passage. The passage is a whole
            chunk, so the range can be wider than the text that matched.
        snippet: The first characters of the passage text.
        score: An ordering value. Higher scores rank first within one result. A
            score is not a confidence, and it is not a probability that the
            passage supports a claim. Its scale depends on the legs that found
            the passage.
        legs: The legs that found the passage.
    """

    evidence_id: str
    document_key: str
    title: str
    content_hash: str
    location: EvidenceLocation
    snippet: str
    score: float
    legs: list[DiscoveryLeg]


class LegFailure(BaseModel):
    """A search leg that failed during discovery.

    Attributes:
        leg: The leg that failed.
        message: The error message from the store.
    """

    leg: DiscoveryLeg
    message: str


class DiscoveryResult(BaseModel):
    """The result of one discovery call.

    Attributes:
        status: The overall outcome. A failed leg never shows as NO_MATCH.
        hits: The visible passages, best first. Empty unless status is OK or
            PARTIAL.
        truncated: True when the search reached its candidate ceiling before it
            found ``limit`` visible passages, so more passages may exist.
        index_state: Whether the needed indexes were ready. None when no index
            was checked, which happens for an empty scope.
        failures: The legs that failed. Empty when every leg ran.
    """

    status: DiscoveryStatus
    hits: list[DiscoveryHit] = Field(default_factory=list)
    truncated: bool = False
    index_state: IndexState | None = None
    failures: list[LegFailure] = Field(default_factory=list)


class FetchStatus(StrEnum):
    """The outcome of fetching one evidence id.

    Attributes:
        OK: The text is returned in full.
        PARTIAL: Part of the requested range is covered by no chunk. Only the covered
            part is returned. An id from this outcome names more text than the
            caller received, so it must not be cited as fetched.
        TRUNCATED: The text was cut at ``max_chars``.
        UNAVAILABLE: The id names no evidence this caller may read. Missing ids
            and ids outside the scope give this same outcome.
        MALFORMED: The id does not decode.
        INDEX_NOT_READY: A search index the operation needs is not ready.
            Fetch uses no index, so it does not return this status.
        FAILED: The store failed while reading the evidence.
    """

    OK = "ok"
    PARTIAL = "partial"
    TRUNCATED = "truncated"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    INDEX_NOT_READY = "index_not_ready"
    FAILED = "failed"


class VersionStatus(StrEnum):
    """Whether the fetched text is the current version of its document.

    Attributes:
        CURRENT: The content hash equals the document's current content hash.
        SUPERSEDED: The document has changed since this text was written. The
            text is still returned, and it is not discoverable.
    """

    CURRENT = "current"
    SUPERSEDED = "superseded"


class FetchOutcome(BaseModel):
    """The result of fetching one evidence id.

    Attributes:
        evidence_id: The id that was requested, as given.
        status: The outcome of the fetch.
        text: The returned text, or None when no text is returned.
        reference: The decoded reference, or None for a malformed id.
        document_key: The key of the document, when the document is readable.
        content_hash: The full content hash of the version the text came from.
        status_of_version: Whether that version is current, when text is
            returned.
        observed_activation_seq: The document activation sequence observed in
            the same read as the text, including for a superseded version.
        covered_range: The offsets of the returned text, when it is a text
            range. A partial range gives the covered part only.
        partial: True when the requested range was not fully covered by chunks.
        detail: A short message for a malformed or failed id. It is None for an
            unavailable id, because the reason stays on the server side.
    """

    evidence_id: str
    status: FetchStatus
    text: str | None = None
    reference: EvidenceReference | None = None
    document_key: str | None = None
    content_hash: str | None = None
    status_of_version: VersionStatus | None = None
    observed_activation_seq: int | None = None
    covered_range: tuple[int, int] | None = None
    partial: bool = False
    detail: str | None = None


class CitationVerdict(StrEnum):
    """Whether a citation traces to evidence the caller fetched.

    Attributes:
        VALID: The id decodes, is in scope, and was fetched, or lies inside a
            fetched span of the same version.
        NOT_FETCHED: The id is in scope but was not fetched, or it reaches past
            every fetched span.
        UNAVAILABLE: The id names a document outside the scope.
        MALFORMED: The id does not decode.
    """

    VALID = "valid"
    NOT_FETCHED = "not_fetched"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"


class CitationCheck(BaseModel):
    """The verdict for one cited evidence id.

    Attributes:
        cited_id: The cited id, as given.
        verdict: The verdict for that id.
    """

    cited_id: str
    verdict: CitationVerdict


class FetchResult(BaseModel):
    """The outcomes of one fetch call.

    Attributes:
        outcomes: One outcome for each fetched id, in the order given. A serving
            layer may drop trailing outcomes to stay within a size limit.
        truncated: True when the serving layer dropped outcomes to stay within
            a size limit.
    """

    outcomes: list[FetchOutcome] = Field(default_factory=list)
    truncated: bool = False


class CitationResult(BaseModel):
    """The verdicts of one citation check call.

    Attributes:
        checks: One verdict for each cited id, in the order given.
        truncated: True when trailing checks were dropped to stay within a
            serving layer's response-size limit.
    """

    checks: list[CitationCheck] = Field(default_factory=list)
    truncated: bool = False
