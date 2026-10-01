"""Dataset adapters and the domain registry."""

from benchmarks.datasets.base import DOMAINS
from benchmarks.datasets.financial import DOMAIN as FINANCIAL
from benchmarks.datasets.legal import DOMAIN as LEGAL


DOMAINS["legal"] = LEGAL
DOMAINS["financial"] = FINANCIAL
