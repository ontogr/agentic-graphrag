"""Dataset adapters and the domain registry."""

from benchmarks.datasets.base import DOMAINS
from benchmarks.datasets.legal import DOMAIN as LEGAL


DOMAINS["legal"] = LEGAL
