"""Checks the committed KPI-EDGAR gold slice against its schema.

The slice comes from ``tests/fixtures/eval/extraction/build_kpi_edgar_fixture.py``.
These checks fail when a rebuilt file has a span that no longer reads back from
its text, or a label or relation the schema does not declare.
"""

from pathlib import Path

import pytest

from agrag.common.data_models.graph_schema import GraphSchema
from agrag.eval import ExtractionGold


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "eval" / "extraction"


@pytest.fixture(scope="module")
def schema() -> GraphSchema:
    """Load the fixture schema."""
    return GraphSchema.model_validate_json((FIXTURE_DIR / "schema.json").read_text())


@pytest.fixture(scope="module")
def items() -> list[ExtractionGold]:
    """Load every gold item of the slice."""
    lines = (FIXTURE_DIR / "kpi_edgar_test_slice.jsonl").read_text().splitlines()
    return [ExtractionGold.model_validate_json(line) for line in lines]


class TestKpiEdgarFixture:
    """The gold slice is well formed and matches its schema."""

    def test_ids_are_unique(self, items: list[ExtractionGold]) -> None:
        """Chunk ids derive from item ids, so a repeat would merge two chunks."""
        assert len({item.id for item in items}) == len(items) >= 15

    def test_every_span_reads_back_from_the_text(
        self, items: list[ExtractionGold]
    ) -> None:
        """Each entity's offsets select exactly its stored text."""
        for item in items:
            for entity in item.gold.entities:
                assert item.text[entity.char_start : entity.char_end] == entity.text

    def test_labels_and_relations_fit_the_schema(
        self, items: list[ExtractionGold], schema: GraphSchema
    ) -> None:
        """Every entity label is declared and every relation matches a pattern."""
        entity_labels = {entity.label for entity in schema.entities}
        patterns = {tuple(pattern) for pattern in schema.relations[0].patterns}
        for item in items:
            entities = item.gold.entities
            assert {e.label for e in entities} <= entity_labels
            for relation in item.gold.relations:
                assert relation.label == schema.relations[0].label
                pair = (
                    entities[relation.source_index].label,
                    entities[relation.target_index].label,
                )
                assert pair in patterns
