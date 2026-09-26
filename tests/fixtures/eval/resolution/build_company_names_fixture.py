"""Build the company name clusters from SEC EDGAR and GLEIF records.

Usage::

    uv run python tests/fixtures/eval/resolution/build_company_names_fixture.py \
        --user-agent "<project name> <contact email>"

The script needs network access and is not part of CI. SEC asks every client to
declare a contact in the User-Agent header, so the flag is required and has no
default. Requests to SEC stay well under its limit of 10 per second.

Companies are picked by hand: ``PICKED_CIKS`` for SEC and ``PICKED_LEIS`` for
GLEIF. A SEC cluster is the current name plus every former name. A GLEIF
cluster is the legal name plus every other name of the record. Names that differ
only by case or surrounding space are one name. For each SEC company the script
adds one hard negative: the most similar name of a different company in
SEC's ticker list. The script stops when one name falls in two clusters.
"""

import argparse
import json
import time
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from agrag.common.text import normalize_text


HERE = Path(__file__).parent
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
GLEIF_RECORD_URL = "https://api.gleif.org/api/v1/lei-records/{lei}"
HARD_NEGATIVE_MIN_RATIO = 0.8
# Seconds between requests. SEC allows 10 per second.
REQUEST_DELAY = 0.25

# Companies with former names give renamed positives. The others give
# single-name clusters that a resolver must leave alone.
PICKED_CIKS = [
    1326801,
    1318605,
    19617,
    1652044,
    1108524,
    796343,
    1075531,
    64803,
    1156039,
    4281,
    1466258,
    1131399,
    1140625,
    879764,
    1045609,
    766704,
    732717,
    865752,
    896159,
    1156375,
    732712,
    831001,
    753308,
    320193,
    789019,
    51143,
    1018724,
    21344,
    886982,
    1403161,
    1141391,
    2488,
    40545,
    18230,
]

# Records with other names, and records with none. GLEIF lists other names of
# the same legal entity, so each cluster is one entity by definition.
PICKED_LEIS = [
    "254900Q9YI74NYMY3648",
    "2549001F9Q96RS08UD12",
    "254900ZR1T6BVSAW4V88",
    "254900VPSGI2D9SH5W46",
    "984500I56838018ADF10",
    "254900G2KY3MXSU44Z57",
    "984500E4B7QDK7B4E606",
    "254900VXMKG9W5SSCA66",
    "254900XZN9ZIV5LLIR85",
    "2549004L5WM5AGKYAE29",
    "25490065UUMJ6QPWHL66",
    "254900O060DOC1R1UM08",
    "254900RCPTHCVEBRG506",
    "254900EQC8Y9U1QDZJ32",
    "254900GVBJ6UPTKUFU66",
    "254900G4Q0LF80KPMN17",
    "254900XOTBLWDULRHL45",
    "254900YBFCSS3L3TYU97",
    "894500SDGD3CZSMA9K46",
    "2549004MS3SPTLFP1P26",
    "98450000E2F80C7EE021",
]


def fetch_json(url: str, user_agent: str) -> Any:
    """Fetch and parse one JSON document."""
    time.sleep(REQUEST_DELAY)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        return json.load(response)


def distinct(names: list[str]) -> list[str]:
    """Keep the first name of each group that normalizes the same."""
    seen: dict[str, str] = {}
    for name in names:
        seen.setdefault(normalize_text(name), name.strip())
    return list(seen.values())


def sec_cluster(cik: int, user_agent: str) -> dict[str, Any]:
    """Build the cluster of one SEC registrant."""
    record = fetch_json(SEC_SUBMISSIONS_URL.format(cik=cik), user_agent)
    former = [entry["name"] for entry in record.get("formerNames", [])]
    return {
        "id": f"sec:{cik}",
        "source": "sec",
        "names": distinct([record["name"], *former]),
        "hard_negative_of": None,
    }


def gleif_cluster(lei: str, user_agent: str) -> dict[str, Any]:
    """Build the cluster of one GLEIF record."""
    entity = fetch_json(GLEIF_RECORD_URL.format(lei=lei), user_agent)["data"][
        "attributes"
    ]["entity"]
    others = [
        entry["name"]
        for key in ("otherNames", "transliteratedOtherNames")
        for entry in entity.get(key) or []
    ]
    return {
        "id": f"gleif:{lei}",
        "source": "gleif",
        "names": distinct([entity["legalName"]["name"], *others]),
        "hard_negative_of": None,
    }


def hard_negatives(
    clusters: list[dict[str, Any]], tickers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Add the most similar name of another company to each SEC cluster."""
    taken = {normalize_text(n) for c in clusters for n in c["names"]}
    picked = {int(c["id"].split(":")[1]) for c in clusters if c["source"] == "sec"}
    companies: dict[int, str] = {}
    for row in tickers:
        companies.setdefault(row["cik_str"], row["title"])
    added = []
    for cluster in clusters:
        if cluster["source"] != "sec":
            continue
        best_name, best_ratio = None, 0.0
        for cik, title in companies.items():
            if cik in picked or normalize_text(title) in taken:
                continue
            ratio = max(
                fuzz.token_sort_ratio(normalize_text(name), normalize_text(title))
                for name in cluster["names"]
            )
            if ratio > best_ratio:
                best_name, best_ratio = title, ratio
        if best_name is not None and best_ratio >= HARD_NEGATIVE_MIN_RATIO * 100:
            taken.add(normalize_text(best_name))
            added.append(
                {
                    "id": f"sec-hard-negative:{cluster['id'].split(':')[1]}",
                    "source": "sec",
                    "names": [best_name],
                    "hard_negative_of": cluster["id"],
                }
            )
    return added


def check_no_shared_names(clusters: list[dict[str, Any]]) -> None:
    """Stop when one normalized name is in two clusters."""
    owner: dict[str, str] = {}
    for cluster in clusters:
        for name in cluster["names"]:
            key = normalize_text(name)
            if owner.setdefault(key, cluster["id"]) != cluster["id"]:
                raise SystemExit(f"{name!r} is in {owner[key]} and {cluster['id']}")


def main() -> None:
    """Fetch the records and write ``company_clusters.json``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--output", type=Path, default=HERE / "company_clusters.json")
    args = parser.parse_args()

    clusters = [sec_cluster(cik, args.user_agent) for cik in PICKED_CIKS]
    clusters += [gleif_cluster(lei, args.user_agent) for lei in PICKED_LEIS]
    tickers = list(fetch_json(SEC_TICKERS_URL, args.user_agent).values())
    clusters += hard_negatives(clusters, tickers)
    check_no_shared_names(clusters)
    args.output.write_text(
        json.dumps(
            {"fetched": date.today().isoformat(), "clusters": clusters}, indent=1
        )
        + "\n"
    )
    multi = sum(len(c["names"]) > 1 for c in clusters)
    print(f"{len(clusters)} clusters, {multi} with more than one name")


if __name__ == "__main__":
    main()
