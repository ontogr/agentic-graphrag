"""Command line: ``python -m benchmarks run|dry-run|report|clean``."""

import argparse
import asyncio
import os
import sys

from benchmarks.datasets.base import DOMAINS
from benchmarks.harness.config import BENCH_CHUNKING, COST_MODEL
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
from benchmarks.harness.services import SERVICE_PORTS, Services
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


def _environment() -> RunEnvironment:
    """Build the agrag environment from the process environment."""
    settings = AgragSettings.from_env()
    agent = settings.agent.clients[0]
    judge = settings.judge
    extractor = settings.extraction.clients[0]
    embedder = AgragSystem.default_embedder_model()

    def make_system(context: SystemContext) -> AgragSystem:
        return AgragSystem(
            store=context.store,
            schema=context.schema,
            chunking=BENCH_CHUNKING,
            documents=context.documents,
            settings=settings,
            tracer=context.tracer,
        )

    return RunEnvironment(
        system_name="agrag",
        code=code_identity(),
        chunking=BENCH_CHUNKING,
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
        agent_config=settings.agent_loop.model_dump(),
        make_system=make_system,
        make_judge=settings.make_judge,
        confirm=_confirm,
        trace_repo=os.environ.get("BENCH_TRACE_REPO"),
        cost=COST_MODEL,
        embedder_model=embedder,
    )


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

    domain = _domain(args.domain)
    try:
        if args.command == "dry-run":
            options = RunOptions(
                max_llm_calls=args.max_llm_calls, max_tokens=args.max_tokens
            )
            plan = make_plan(
                args.domain,
                domain,
                args.mode,
                options,
                chunking=BENCH_CHUNKING,
                cost=COST_MODEL,
            )
            print(
                f"chunks {plan.bound.chunks}\n"
                f"LLM calls (upper bound) {plan.bound.llm_calls}\n"
                f"tokens (upper bound) {plan.bound.tokens}\n"
                f"cap {plan.cap.llm_calls} calls, {plan.cap.tokens} tokens"
            )
            return 0
        record, path = asyncio.run(
            run(args.domain, domain, args.mode, _options(args), _environment())
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
