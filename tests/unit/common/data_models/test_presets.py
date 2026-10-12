"""Verify applying schema presets preserves base behavior without shared mutation."""

import pytest

from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.presets import LEGAL, OPERATIONS, Preset


class TestPresetApply:
    """Preset application composes independent schema values."""

    def test_combined_presets_keep_base_relations_and_add_only_new_types(self) -> None:
        """Presets add their entity types without extending relation patterns."""
        combined = LEGAL.apply(OPERATIONS.apply(DEFAULT_SCHEMA))

        assert combined.name == "default+operations+legal"
        assert combined.version == DEFAULT_SCHEMA.version
        assert [entity.label for entity in combined.entities[-5:]] == [
            "Facility",
            "Service",
            "Occupation",
            "Contract",
            "Regulation",
        ]
        assert combined.relations == DEFAULT_SCHEMA.relations
        assert not combined.allows("LOCATED_IN", "Facility", "Location")

    def test_result_does_not_share_mutable_base_or_preset_models(self) -> None:
        """Mutating the returned schema cannot alter either input model."""
        base = GraphSchema.model_validate(DEFAULT_SCHEMA.model_dump())
        preset = Preset(
            name="custom",
            entities=[EntityType(label="Widget", description="A manufactured item.")],
        )
        result = preset.apply(base)

        result.entities[0].description = "Changed in the result."
        result.relations[0].patterns.clear()

        assert base.entities[0].description == "A person, living, dead, or fictional."
        assert base.relations[0].patterns == [("Person", "Organization")]
        assert preset.entities[0].description == "A manufactured item."

    def test_rejects_reapplying_preset_to_existing_label(self) -> None:
        """A preset cannot duplicate a type already present in the base."""
        with pytest.raises(ValueError, match="already declares 'Facility'"):
            OPERATIONS.apply(OPERATIONS.apply(DEFAULT_SCHEMA))
