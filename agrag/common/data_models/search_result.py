"""One retrieved item, tagged with source and relevance score."""

from typing import Union
from uuid import UUID

from pydantic import BaseModel

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.resolved_entity import ResolvedEntity


class SearchResult(BaseModel):
    """One retrieved item, tagged with where it came from.

    Attributes:
        item: The retrieved Entity, ResolvedEntity, Relation, Chunk, or
            Community, already resolved through any merged_into chain.
        score: The method's own relevance score. Not comparable
            across methods until Fusion normalizes it.
        method: The name of the retrieval method that produced
            this result.
    """

    item: Union[Entity, ResolvedEntity, Relation, Chunk, Community]
    score: float
    method: str

    @property
    def identity_key(self) -> tuple[str, UUID]:
        """Return the (type, id) key Fusion deduplicates on.

        Raises:
            ValueError: The item has no id, so it cannot be
                deduplicated.
        """
        item_id = self.item.id
        if item_id is None:
            raise ValueError(
                f"{type(self.item).__name__} has no id and cannot be deduplicated."
            )
        return (type(self.item).__name__, item_id)
