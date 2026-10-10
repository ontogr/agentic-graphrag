"""Tests the ingest cache key and the marker that the harness stores in the graph."""

import pytest

from benchmarks.harness import cache
from benchmarks.harness.record import PathUsage
from tests.unit.benchmarks.fakes import DOMAIN, FakeStore


def _key(**changes) -> str:
    manifest = DOMAIN.adapter.load("lite")
    values = {
        "manifest": manifest,
        "corpus_id": "c1",
        "schema_sha256": "s",
        "extractor_model": "m",
        "embedder_model": "e",
        "chunking_fingerprint": "f",
        "agrag_tree": "t",
        "benchmarks_code_sha256": "b",
        "uv_lock_sha256": "l",
    }
    return cache.cache_key(**{**values, **changes})


class TestCacheKey:
    """The inputs that change the ingest cache key."""

    def test_is_stable_for_the_same_inputs(self):
        """Is stable for the same inputs."""
        assert _key() == _key()

    @pytest.mark.parametrize(
        "change",
        [
            {"schema_sha256": "s2"},
            {"extractor_model": "m2"},
            {"embedder_model": "e2"},
            {"chunking_fingerprint": "f2"},
            {"agrag_tree": "t2"},
            {"benchmarks_code_sha256": "b2"},
            {"uv_lock_sha256": "l2"},
            {"corpus_id": "c2"},
        ],
    )
    def test_changes_when_an_input_changes(self, change):
        """Changes when an input changes."""
        assert _key(**change) != _key()

    def test_changes_when_a_corpus_document_changes(self):
        """Changes when a corpus document changes."""
        manifest = DOMAIN.adapter.load("lite")
        manifest.corpora[0].documents[0].sha256 = "changed"

        assert _key(manifest=manifest) != _key()

    def test_ignores_documents_of_other_corpora(self):
        """Ignores documents of other corpora."""
        manifest = DOMAIN.adapter.load("lite")
        manifest.corpora[1].documents[0].sha256 = "changed"

        assert _key(manifest=manifest) == _key()


class TestMarker:
    """The marker stored in the graph after an ingest."""

    async def test_round_trips_key_usage_and_empty_extractions(self):
        """Round trips key usage and empty extractions."""
        store = FakeStore({})
        marker = cache.IngestMarker("k", PathUsage(llm_calls=2, input_tokens=5), 1)

        await cache.write_marker(store, marker)

        assert await cache.read_marker(store) == marker
