"""Dataset adapters and the domain registry."""

from benchmarks.datasets.base import DOMAINS
from benchmarks.datasets.financial import DOMAIN as FINANCIAL
from benchmarks.datasets.graphrag_general import DOMAIN as GRAPHRAG_GENERAL
from benchmarks.datasets.healthcare import DOMAIN as HEALTHCARE
from benchmarks.datasets.legal import DOMAIN as LEGAL
from benchmarks.datasets.memory import DOMAIN as MEMORY


DOMAINS["legal"] = LEGAL
DOMAINS["financial"] = FINANCIAL
DOMAINS["graphrag_general"] = GRAPHRAG_GENERAL
DOMAINS["memory"] = MEMORY
DOMAINS["healthcare"] = HEALTHCARE
