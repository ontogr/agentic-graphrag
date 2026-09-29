"""The report: a Markdown table of committed records."""

from pathlib import Path

from benchmarks.harness.record import RECORD_NAME, RESULTS_DIR, RunRecord


_COLUMNS = (
    "domain",
    "mode",
    "agent model",
    "judge model",
    "chunking",
    "n",
    "scores",
    "LLM calls",
    "tokens",
    "code",
    "date",
)


def load_records(results: Path = RESULTS_DIR) -> list[RunRecord]:
    """Read every committed record, oldest first."""
    records = [
        RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for path in results.glob(f"*/*/{RECORD_NAME}")
    ]
    return sorted(records, key=lambda record: record.created_at)


def _key(record: RunRecord) -> tuple[str, ...]:
    """Group runs that are comparable: same domain, mode, models and chunking."""
    return (
        record.domain,
        record.mode,
        record.models["agent"]["model_id"],
        record.models["judge"]["model_id"],
        record.chunking.fingerprint,
    )


def _row(record: RunRecord) -> list[str]:
    scores = ", ".join(
        f"{name} {score.mean:.2f}"
        for name, score in sorted(record.scores.aggregate.items())
    )
    usage = record.usage
    return [
        record.domain,
        record.mode,
        record.models["agent"]["model_id"],
        record.models["judge"]["model_id"],
        record.chunking.fingerprint[:8],
        str(record.dataset.n_questions),
        scores,
        str(usage.llm_calls),
        str(usage.input_tokens + usage.output_tokens),
        record.code.git_describe,
        record.created_at[:10],
    ]


def report(
    records: list[RunRecord], *, show_all: bool = False, domain: str | None = None
) -> str:
    """Render records as a Markdown table.

    Args:
        records: The records, oldest first.
        show_all: List every record. Without it, only the newest record of each
            domain, mode, agent model, judge model and chunking.
        domain: Show only this domain.

    Returns:
        The table, and a warning for each domain with runs on more than one model.
        Every score comes from the model that judged it, and that model may be the
        one that answered, which raises scores.
    """
    if domain is not None:
        records = [record for record in records if record.domain == domain]
    shown = records if show_all else list({_key(r): r for r in records}.values())
    lines = [
        "| " + " | ".join(_COLUMNS) + " |",
        "|" + "---|" * len(_COLUMNS),
        *("| " + " | ".join(_row(record)) + " |" for record in shown),
    ]
    models: dict[str, set[tuple[str, str]]] = {}
    for record in shown:
        models.setdefault(record.domain, set()).add(
            (record.models["agent"]["model_id"], record.models["judge"]["model_id"])
        )
    lines.extend(
        f"\nWarning: {name} has runs on {len(found)} model pairs. "
        "Do not compare or average them."
        for name, found in sorted(models.items())
        if len(found) > 1
    )
    return "\n".join(lines)
