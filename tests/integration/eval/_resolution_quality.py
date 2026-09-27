"""Loads the company name clusters used by the resolution quality tests."""

from pathlib import Path

from pydantic import BaseModel

from agrag.eval import ClusterAssignment


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "eval" / "resolution"


class CompanyCluster(BaseModel):
    """The names of one legal entity.

    Attributes:
        id: A stable id that names the source record.
        source: ``sec`` or ``gleif``.
        names: Every name of the entity, as written in the source.
        hard_negative_of: The id of the cluster whose name this one resembles,
            or ``None``.
    """

    id: str
    source: str
    names: list[str]
    hard_negative_of: str | None


class CompanyClusters(BaseModel):
    """The fixture file.

    Attributes:
        fetched: The date the records were fetched.
        clusters: The clusters.
    """

    fetched: str
    clusters: list[CompanyCluster]


def load_company_clusters() -> CompanyClusters:
    """Read the committed fixture."""
    return CompanyClusters.model_validate_json(
        (FIXTURE_DIR / "company_clusters.json").read_text()
    )


def mentions_and_gold(
    clusters: list[CompanyCluster],
) -> tuple[list[str], ClusterAssignment]:
    """Flatten clusters into mention strings and their gold assignment."""
    mentions: list[str] = []
    groups: list[list[int]] = []
    for cluster in clusters:
        groups.append(list(range(len(mentions), len(mentions) + len(cluster.names))))
        mentions += cluster.names
    return mentions, ClusterAssignment(size=len(mentions), clusters=groups)
