"""Verify the default schema accepts only the intended domain relations."""

from agrag.common.data_models.default_schema import DEFAULT_SCHEMA


class TestDefaultSchema:
    """The shipped schema provides a closed set of useful relation patterns."""

    def test_allows_declared_pairs_and_rejects_wrong_direction_or_type(self) -> None:
        """A declared relation accepts its pair and rejects nearby invalid pairs."""
        assert DEFAULT_SCHEMA.allows("WORKS_FOR", "Person", "Organization")
        assert not DEFAULT_SCHEMA.allows("WORKS_FOR", "Organization", "Person")
        assert not DEFAULT_SCHEMA.allows("WORKS_FOR", "Person", "Event")
        assert not DEFAULT_SCHEMA.allows("RELATED_TO", "Person", "Event")

    def test_general_relation_families_accept_their_intended_targets(self) -> None:
        """Ownership, authorship, participation and dependency stay typed."""
        assert DEFAULT_SCHEMA.allows("PART_OF", "Project", "Project")
        assert DEFAULT_SCHEMA.allows("LOCATED_IN", "Event", "Location")
        assert DEFAULT_SCHEMA.allows("OWNS", "Organization", "Dataset")
        assert DEFAULT_SCHEMA.allows("AUTHORED", "Person", "Publication")
        assert DEFAULT_SCHEMA.allows("PARTICIPATED_IN", "Organization", "Event")
        assert DEFAULT_SCHEMA.allows("DEPENDS_ON", "Software", "Dataset")
        assert DEFAULT_SCHEMA.allows("SUPPLIES", "Organization", "Product")
        assert not DEFAULT_SCHEMA.allows("DEPENDS_ON", "Dataset", "Software")
