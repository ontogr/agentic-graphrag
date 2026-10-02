"""Command line: ``python -m benchmarks run|dry-run|report|clean|healthcare``."""

import argparse
import asyncio
import sys

from agrag.chunking import Chunking, RecursiveChunker
from benchmarks.datasets.base import DOMAINS
from benchmarks.datasets.healthcare_index import INDEX_PATH, build_index, check_index
from benchmarks.harness.config import BENCH_CHUNKING, COST_MODEL, RUN_LIMITS
from benchmarks.harness.dry_run import DryRun, SpendCapError
from benchmarks.harness.record import code_identity
from benchmarks.harness.report import load_records, report
from benchmarks.harness.runner import (
    RunEnvironment,
    RunOptions,
    RunRefusedError,
    SystemContext,
    make_plan,
    run,
)
from benchmarks.harness.services import SERVICE_PORTS, BenchSettings, Services
from benchmarks.systems.agrag import AgragSettings, AgragSystem


def _confirm(bound: DryRun) -> bool:
    """Ask on the terminal whether to start a full run."""
    if not sys.stdin.isatty():
        return False
    answer = input(
        f"Full run: up to {bound.llm_calls} LLM calls and {bound.tokens} tokens. "
        "Continue? [y/N] "
    )
    return answer.strip().lower() == "y"


def _environment(chunking: Chunking, domain: str, mode: str) -> RunEnvironment:
    """Build the agrag environment from the process environment."""
    limits = RUN_LIMITS.get((domain, mode))
    settings = AgragSettings.from_env(limits)
    agent = settings.agent.clients[0]
    judge = settings.judge
    extractor = settings.extraction.clients[0]
    embedder = AgragSystem.default_embedder_model()

    def make_system(context: SystemContext) -> AgragSystem:
        return AgragSystem(
            store=context.store,
            schema=context.schema,
            chunking=chunking,
            documents=context.documents,
            settings=settings,
            tracer=context.tracer,
        )

    return RunEnvironment(
        system_name="agrag",
        code=code_identity(),
        chunking=chunking,
        models={
            "agent": {"model_id": agent.model, "provider": agent.provider},
            "judge": {
                "model_id": judge.client.model,
                "provider": judge.client.provider,
                "temperature": judge.temperature,
            },
            "extractor": {"model_id": extractor.model, "provider": extractor.provider},
            "embedder": {"model": embedder},
        },
        agent_config={
            **settings.agent_loop.model_dump(),
            "max_llm_pairs": settings.max_llm_pairs,
        },
        make_system=make_system,
        make_judge=settings.make_judge,
        confirm=_confirm,
        trace_repo=BenchSettings().trace_repo,
        cost=limits.cost if limits else COST_MODEL,
        embedder_model=embedder,
    )


def _chunking(args: argparse.Namespace) -> Chunking:
    """Return the benchmark chunking, or characters-per-chunk chunking if asked."""
    if args.chunk_size is None:
        return BENCH_CHUNKING
    return Chunking(
        fallback=RecursiveChunker(tokenizer="character", chunk_size=args.chunk_size)
    )


def _build_index(*, check: bool) -> int:
    """Build the MedCorp search index, and check it against the fixtures if asked."""
    rows = build_index()
    print(f"index {INDEX_PATH}: {rows} passages")
    if not check:
        return 0
    rows, problems = check_index()
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def _domain(name: str):
    """Look up a registered domain or exit with the list of known ones."""
    if name not in DOMAINS:
        known = ", ".join(sorted(DOMAINS)) or "none yet"
        sys.exit(f"unknown domain {name!r}; registered domains: {known}")
    return DOMAINS[name]


def _options(args: argparse.Namespace) -> RunOptions:
    return RunOptions(
        concurrency=args.concurrency,
        question_timeout_s=args.question_timeout,
        max_llm_calls=args.max_llm_calls,
        max_tokens=args.max_tokens,
        yes=args.yes,
    )


def _positive_int(text: str) -> int:
    """Parse a command-line integer that must be at least one."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"{text} is not a positive integer")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m benchmarks", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def add_target(command: argparse.ArgumentParser) -> None:
        command.add_argument("domain")
        command.add_argument("--mode", choices=("lite", "full"), required=True)
        command.add_argument("--max-llm-calls", type=int)
        command.add_argument("--max-tokens", type=int)
        command.add_argument(
            "--chunk-size",
            type=_positive_int,
            help="Chunk size in characters. The default is about 1000 tokens.",
        )

    run_command = commands.add_parser("run", help="Ingest, answer, grade and record.")
    add_target(run_command)
    run_command.add_argument("--yes", action="store_true", help="Skip the prompt.")
    run_command.add_argument("--concurrency", type=_positive_int, default=2)
    run_command.add_argument("--question-timeout", type=float, default=900.0)
    add_target(commands.add_parser("dry-run", help="Bound the cost without a model."))
    report_command = commands.add_parser("report", help="Print committed records.")
    report_command.add_argument("--all", action="store_true")
    report_command.add_argument("--domain")
    clean = commands.add_parser("clean", help="Delete corpus graphs and volumes.")
    clean.add_argument("--corpus", help="The service name of one corpus.")
    healthcare = commands.add_parser("healthcare", help="Healthcare corpus tools.")
    healthcare_commands = healthcare.add_subparsers(dest="action", required=True)
    build_index = healthcare_commands.add_parser(
        "build-index", help="Build the MedCorp search index."
    )
    build_index.add_argument(
        "--check", action="store_true", help="Check the index against the fixtures."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    args = _parser().parse_args(argv)
    if args.command == "report":
        print(report(load_records(), show_all=args.all, domain=args.domain))
        return 0
    if args.command == "clean":
        services = Services()
        for service in [args.corpus] if args.corpus else sorted(SERVICE_PORTS):
            services.remove(service)
        return 0

    if args.command == "healthcare":
        return _build_index(check=args.check)

    domain = _domain(args.domain)
    try:
        limits = RUN_LIMITS.get((args.domain, args.mode))
        if args.command == "dry-run":
            options = RunOptions(
                max_llm_calls=args.max_llm_calls, max_tokens=args.max_tokens
            )
            plan = make_plan(
                args.domain,
                domain,
                args.mode,
                options,
                chunking=_chunking(args),
                cost=limits.cost if limits else COST_MODEL,
            )
            print(
                f"chunks {plan.bound.chunks}\n"
                f"LLM calls (estimate) {plan.bound.llm_calls}\n"
                f"tokens (estimate) {plan.bound.tokens}\n"
                f"cap {plan.cap.llm_calls} calls, {plan.cap.tokens} tokens"
            )
            return 0
        record, path = asyncio.run(
            run(
                args.domain,
                domain,
                args.mode,
                _options(args),
                _environment(_chunking(args), args.domain, args.mode),
            )
        )
    except (SpendCapError, RunRefusedError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(f"wrote {path}")
    if not record.lands_in_results:
        print("not committed: the tree is dirty or usage is incomplete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
