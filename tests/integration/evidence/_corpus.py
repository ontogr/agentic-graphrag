"""Authored corpus and fake models for the evidence integration tests.

The corpus is three short documents written for these tests. The gold
passages are located by searching the authored text for a sentence, never by
calling the code under test.

The embedder is a deterministic bag of words. Words map to four axes, one per
topic group, and each text gets a small constant on every axis so no vector is
zero. The Chunk vector index in the shared test database has four dimensions,
so the vectors use four axes as well.
"""

import hashlib
import re
from collections.abc import Sequence

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.evidence import EvidenceKind, EvidenceReference
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.embedding.base import Embedder
from agrag.evidence.ids import encode_evidence_id
from agrag.ingestion.extract import Extractor


VECTOR_DIMENSIONS = 4

_AXES: dict[str, int] = {
    **dict.fromkeys(
        ["privacy", "notice", "data", "personal", "collect", "contacts", "phone"], 0
    ),
    **dict.fromkeys(
        ["keep", "upload", "activity", "database", "records", "servers", "kept"], 1
    ),
    **dict.fromkeys(
        ["lighthouse", "harbor", "lantern", "crew", "gasket", "keeper", "boat"], 2
    ),
    **dict.fromkeys(["viber", "messaging", "app", "messages", "calls"], 3),
}

GOLD_SENTENCE = (
    "We keep and upload your activity to our database so that we can improve "
    "the service."
)

KEEP_TEXT = "\n\n".join(
    [
        "Keep Privacy Notice. This notice explains what the Keep messaging app "
        "collects and how it uses that information.",
        "We collect your phone number and the contacts that you choose to sync "
        "with the app.",
        GOLD_SENTENCE,
        "You can turn off activity history at any time in the settings menu.",
        "We do not sell personal data to advertisers.",
        "Questions about this notice can be sent to the support team.",
    ]
)

VIBER_TEXT = "\n\n".join(
    [
        "Viber Privacy Notice. This notice describes the data that the Viber "
        "messaging app processes when you use it.",
        "We keep call and message records only for as long as they are needed "
        "to deliver them.",
        "We upload crash reports to an analytics vendor so that we can fix bugs.",
        "Activity on public channels may be visible to other users of the app.",
        "Your contacts are stored on our servers until you delete your account.",
        "Account data is kept in a separate database in the European Union.",
    ]
)

HARBOR_SENTENCE = (
    "The crew replaced the copper lantern gasket on the third landing during the "
    "spring inspection."
)

_HARBOR_PARAGRAPHS = [
    "Harbor Lighthouse Maintenance Log. This log records the repairs and "
    "inspections of the lighthouse on the north headland.",
    "The keeper opened the log in January and recorded the weather for each day "
    "of the month.",
    "Winter storms cracked two panes in the lantern room, so the crew sealed them "
    "with clear resin.",
    "In February the lighthouse generator failed during a night shift, and the "
    "backup battery kept the lamp running.",
    HARBOR_SENTENCE + " The old gasket showed salt corrosion along the upper seam.",
    "Salt air had worn the iron railings on the gallery, so painters stripped them "
    "back to bare metal.",
    "The fog signal was tested every Monday at dawn, and the results went into the "
    "ledger beside the lighthouse lamp logs.",
    "A supply boat delivered oil, spare bulbs and a new lens cleaning kit at the "
    "end of April.",
    "The keeper reported a cracked step on the spiral stair, and the district "
    "office scheduled a welder for June.",
    "During the summer the lighthouse was repainted white with a red band, matching "
    "the chart symbol.",
    "Visitors were allowed on the gallery on two days each week, under the "
    "supervision of a volunteer guide.",
    "The final entry of the season recorded the first autumn gale and the damage "
    "to the boathouse roof.",
]

HARBOR_TEXT = "\n\n".join(_HARBOR_PARAGRAPHS)

# The second version replaces the gasket sentence and ends with a newline that
# no chunk covers, so an exact fetch over the tail returns a partial range.
HARBOR_TEXT_V2 = (
    "\n\n".join(
        [
            _HARBOR_PARAGRAPHS[0],
            _HARBOR_PARAGRAPHS[1],
            _HARBOR_PARAGRAPHS[2],
            _HARBOR_PARAGRAPHS[3],
            "The crew replaced the brass lantern gasket on the third landing during "
            "the autumn inspection. The lighthouse crew logged the new seal.",
            *_HARBOR_PARAGRAPHS[5:],
        ]
    )
    + "\n"
)


def sha256_of(text: str) -> str:
    """Return the sha256 hex digest of text as the lifecycle hashes it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def locate(text: str, sentence: str) -> tuple[int, int]:
    """Return the (start, end) offsets of an authored sentence in text.

    Raises:
        AssertionError: The sentence does not occur exactly once in text.
    """
    assert text.count(sentence) == 1, "authored sentence must occur once"
    start = text.index(sentence)
    return start, start + len(sentence)


class BagOfWordsEmbedder(Embedder):
    """Embedder that counts topic words on four fixed axes."""

    model = "bag-of-words"

    async def dimensions(self) -> int:
        """Return the number of axes."""
        return VECTOR_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one count vector per text, with a small constant on each axis."""
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.01] * VECTOR_DIMENSIONS
            for word in re.findall(r"[a-z]+", text.lower()):
                axis = _AXES.get(word)
                if axis is not None:
                    vector[axis] += 1.0
            vectors.append(vector)
        return vectors


class NoEntityExtractor(Extractor):
    """Extractor that finds no entities, so no LLM or GLiNER model runs."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return an empty extraction result."""
        return ExtractionResult(entities=[], relations=[], extractor_name="fake")


def make_document(key: str, text: str) -> Document:
    """Build a prose Document with an explicit document key."""
    return Document(
        text=text,
        title=key.rsplit("/", 1)[-1],
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=sha256_of(text),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=text.count("\n") + 1,
    )


def span_evidence_id(document_key: str, text: str, start: int, end: int) -> str:
    """Return the span evidence id of a range in one version of a document.

    The id names the Document node of document_key and the sha256 prefix of the
    version text. It does not read the store, so tests can build ids for text
    they wrote, including ids the store does not hold.
    """
    return encode_evidence_id(
        EvidenceReference(
            kind=EvidenceKind.SPAN,
            document_node_id=Document.node_id_for(document_key=document_key),
            content_hash_prefix=sha256_of(text)[:16],
            char_start=start,
            char_end=end,
        )
    )
