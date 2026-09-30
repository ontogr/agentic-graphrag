"""Guard that the Configuration page matches the settings classes."""

import re
from pathlib import Path

import pytest
from pydantic import SecretStr

from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.embedding.settings import EmbeddingSettings
from agrag.graphdb.settings import Neo4jSettings
from agrag.ingestion.extract import ExtractionLLMSettings
from agrag.ingestion.settings import CutoverJobSettings
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.settings import MilvusSettings, QdrantSettings, WeaviateSettings


_PAGE = Path(__file__).parents[3] / "docs" / "docs" / "reference" / "configuration.mdx"
_ROWS = {
    m[1]: m[0]
    for m in re.finditer(
        r"^\| `([A-Z][A-Z0-9_]+)` \|.*$", _PAGE.read_text(), re.MULTILINE
    )
}

# Read by the from_openai_compatible_env helpers, not by a settings field.
_HELPER_VARIABLES = {
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL_ID",
    "AGENT_LLM_BASE_URL",
    "AGENT_LLM_API_KEY",
    "AGENT_LLM_MODEL_ID",
    "EVAL_JUDGE_BASE_URL",
    "EVAL_JUDGE_API_KEY",
    "EVAL_JUDGE_MODEL_ID",
}
_REQUIRED = object()
_CLASSES = [
    AgentLLMSettings,
    AgentSettings,
    CutoverJobSettings,
    EmbeddingSettings,
    ExtractionLLMSettings,
    MilvusSettings,
    Neo4jSettings,
    QdrantSettings,
    RetrievalSettings,
    WeaviateSettings,
]


def _fields() -> dict[str, object]:
    """Return every env variable name mapped to its default or ``_REQUIRED``."""
    from agrag.eval.settings import EvalJudgeSettings  # noqa: PLC0415

    found: dict[str, object] = {}
    for cls in [*_CLASSES, EvalJudgeSettings]:
        prefix = cls.model_config["env_prefix"]
        for name, field in cls.model_fields.items():
            found[f"{prefix}{name}".upper()] = (
                _REQUIRED if field.is_required() else field.default
            )
    return found


def test_page_lists_exactly_the_variables_in_code() -> None:
    """Every settings field is on the page and the page lists nothing else."""
    pytest.importorskip("deepeval")

    assert set(_ROWS) == set(_fields()) | _HELPER_VARIABLES


def test_scalar_defaults_match() -> None:
    """A string, number, or boolean default appears in its row."""
    pytest.importorskip("deepeval")

    for variable, raw in _fields().items():
        default = raw.get_secret_value() if isinstance(raw, SecretStr) else raw
        if default is _REQUIRED or default in ("", None):
            continue
        if not isinstance(default, str | int | float):
            continue
        shown = str(default).lower() if isinstance(default, bool) else str(default)
        assert f"`{shown}`" in _ROWS[variable], variable
