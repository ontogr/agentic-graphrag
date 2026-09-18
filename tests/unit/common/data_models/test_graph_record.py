"""Tests for the UpsertFailure and UpsertResult data models.

Covers UpsertResult's empty default and its round trip through
model_dump/model_validate, since this shape crosses the GraphStore ABC
boundary and later feeds Graph.add()'s own result assembly.
"""

from agrag.common.data_models.graph_record import UpsertFailure, UpsertResult


class TestUpsertResult:
    """An UpsertResult reports how many records wrote and which failed."""

    def test_upsert_result_defaults_to_empty_failures(self) -> None:
        """A default result has no writes and no failures."""
        result = UpsertResult()
        assert result.written == 0
        assert result.failures == []

    def test_upsert_result_round_trips_through_model_dump(self) -> None:
        """A populated result survives a JSON dump and validate cycle."""
        result = UpsertResult(
            written=3,
            failures=[
                UpsertFailure(
                    id="1", error_type="ValueError", error_message="bad label"
                ),
                UpsertFailure(
                    id="2",
                    error_type="GraphStoreConstraintViolationError",
                    error_message="duplicate merge_key",
                ),
            ],
        )
        dumped = result.model_dump(mode="json")
        restored = UpsertResult.model_validate(dumped)
        assert restored == result
