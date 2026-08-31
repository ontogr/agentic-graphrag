"""Citation ledger: assigns and tracks stable keys for one agent run."""

from uuid import UUID

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.search_result import SearchResult


_PREFIX_MAP = {
    "Entity": "E",
    "Relation": "R",
    "Chunk": "C",
}


class Ledger:
    """Assigns and tracks stable citation keys for one agent run.

    A key (E1, R1, C1 for entities, relations, and chunks) is
    assigned the first time this run encounters that item, by
    SearchResult.identity_key, and never reassigned within the run.
    The agent is shown rendered evidence carrying these keys, never
    raw SearchResults.
    """

    def __init__(self) -> None:
        """Initialize an empty ledger."""
        self._key_to_result: dict[str, SearchResult] = {}
        self._identity_to_key: dict[tuple[str, UUID], str] = {}
        self._counters: dict[str, int] = {}

    def cite(self, result: SearchResult) -> str:
        """Return this result's citation key, assigning one if new.

        Args:
            result: The SearchResult to assign a key to.

        Returns:
            The citation key (e.g. ``E1``, ``C3``).
        """
        key_tuple = result.identity_key
        if key_tuple in self._identity_to_key:
            return self._identity_to_key[key_tuple]

        type_name = type(result.item).__name__
        prefix = _PREFIX_MAP.get(type_name, "X")
        count = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = count

        key = f"{prefix}{count}"
        self._identity_to_key[key_tuple] = key
        self._key_to_result[key] = result
        return key

    def render(self, result: SearchResult) -> str:
        """Return the markdown-with-key text the agent sees.

        Args:
            result: The SearchResult to render.

        Returns:
            Markdown text with the citation key and item summary.
        """
        key = self.cite(result)
        item = result.item

        if isinstance(item, Entity):
            return f"[{key}] Entity: {item.name} ({item.label})"
        if isinstance(item, Chunk):
            preview = item.text[:200]
            return f"[{key}] Chunk: {preview}..."
        if isinstance(item, Relation):
            return f"[{key}] Relation: {item.type}({item.source_id}, {item.target_id})"
        return f"[{key}] {type(item).__name__}"

    def resolve(self, key: str) -> SearchResult | None:
        """Return the SearchResult behind a citation key.

        Args:
            key: The citation key to look up.

        Returns:
            The SearchResult, or None if the key is unknown.
        """
        return self._key_to_result.get(key)

    @property
    def keys(self) -> list[str]:
        """Return all citation keys assigned so far."""
        return list(self._key_to_result.keys())
