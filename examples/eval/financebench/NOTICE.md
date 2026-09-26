# Notice: FinanceBench subset

The files in this folder come from FinanceBench, published by Patronus AI.

- `documents/` holds three SEC filings (3M 2018 10-K, American Express 2022
  10-K, Netflix 2017 10-K), copied without change from the FinanceBench
  repository.
- `questions.jsonl` holds five questions with their reference answers, copied
  from `data/financebench_open_source.jsonl` in that repository.

Sources:

- <https://huggingface.co/datasets/PatronusAI/financebench>
- <https://github.com/patronus-ai/financebench>

Licence: the Hugging Face dataset card states CC-BY-NC-4.0. The GitHub
repository states no licence. A copy of the CC-BY-NC-4.0 legal code is in
`LICENSE-CC-BY-NC-4.0`. This licence forbids commercial use. This folder is not
covered by the Apache-2.0 licence of the agrag repository.

Citation:

```bibtex
@misc{islam2023financebench,
  title={FinanceBench: A New Benchmark for Financial Question Answering},
  author={Pranab Islam and Anand Kannappan and Douwe Kiela and Rebecca Qian and Nino Scherrer and Bertie Vidgen},
  year={2023},
  eprint={2311.11944},
  archivePrefix={arXiv},
  primaryClass={cs.CL}
}
```

Paper: <https://arxiv.org/abs/2311.11944>
