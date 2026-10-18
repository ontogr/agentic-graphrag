# Benchmarks

Benchmarks run agrag on public datasets and write a run record with a trace. A run from a clean worktree with complete usage goes under `benchmarks/results/` for commit. Other completed runs go under the ignored `reports/benchmarks/` directory. Full runs with complete usage upload their trace to the configured Hugging Face dataset repository. Lite runs keep the trace beside the record.

```bash
make bench-dry DOMAIN=<name> MODE=lite   # bound the calls and tokens, no model
make bench-lite DOMAIN=<name>            # run the lite set
make bench DOMAIN=<name>                 # run the full set, asks first
uv run python -m benchmarks report       # print the committed records
```

Read the [benchmarks documentation](../docs/docs/benchmarks/index.mdx) for what the
datasets are and how the records are audited. Read
[Run the benchmarks](../docs/docs/benchmarks/run-benchmarks.mdx) for the setup.
