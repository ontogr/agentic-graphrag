"""Checks the committed company name clusters.

The file comes from ``tests/fixtures/eval/resolution/build_company_names_fixture.py``.
A name that normalizes the same in two clusters makes the exact tier merge two
entities that gold keeps apart, so these checks fail on a rebuilt file that has one.
"""

from collections import Counter

from agrag.common.text import normalize_text
from tests.integration.eval._resolution_quality import (
    FIXTURE_DIR,
    load_company_clusters,
    mentions_and_gold,
)


class TestCompanyClustersFixture:
    """The name clusters are consistent and large enough to score."""

    def test_no_name_is_in_two_clusters_or_twice_in_one(self) -> None:
        """Every normalized name is unique across the file."""
        names = [
            normalize_text(name)
            for cluster in load_company_clusters().clusters
            for name in cluster.names
        ]

        assert [n for n, count in Counter(names).items() if count > 1] == []

    def test_hard_negatives_point_at_another_cluster(self) -> None:
        """Each hard negative names an existing cluster and stands alone."""
        clusters = load_company_clusters().clusters
        ids = {cluster.id for cluster in clusters}

        for cluster in clusters:
            if cluster.hard_negative_of is not None:
                assert cluster.hard_negative_of in ids
                assert cluster.hard_negative_of != cluster.id
                assert len(cluster.names) == 1

    def test_has_enough_clusters_of_each_kind(self) -> None:
        """The set holds renamed companies and single-name companies."""
        clusters = load_company_clusters().clusters
        multi = [c for c in clusters if len(c.names) > 1]

        assert len(multi) >= 30
        assert len(clusters) - len(multi) >= 30

    def test_gold_assignment_covers_every_mention_once(self) -> None:
        """Flattening keeps each name in the cluster it came from."""
        clusters = load_company_clusters().clusters
        mentions, gold = mentions_and_gold(clusters)

        assert gold.size == len(mentions) == sum(len(c.names) for c in clusters)
        assert sorted(i for group in gold.clusters for i in group) == list(
            range(gold.size)
        )

    def test_fixture_is_small(self) -> None:
        """The fixture stays under 300 KB."""
        size = sum(p.stat().st_size for p in FIXTURE_DIR.rglob("*") if p.is_file())

        assert size < 300 * 1024
