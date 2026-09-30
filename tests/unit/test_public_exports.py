"""The public import surface resolves on a base install and has no import cycles.

Each package is imported first in a fresh interpreter, so a circular import between
subpackages fails here instead of depending on which module a caller imports first.
Optional dependencies are blocked with an import hook that raises
``ModuleNotFoundError``, which is what a base install without extras does.
"""

import subprocess
import sys
import textwrap

import pytest


PACKAGES = [
    "agrag.agents",
    "agrag.chunking",
    "agrag.common.data_models",
    "agrag.embedding",
    "agrag.graphdb",
    "agrag.ingestion",
    "agrag.loaders",
    "agrag.retrieval",
    "agrag.vectordb",
]

OPTIONAL_MODULES = [
    "baml_py",
    "deepagents",
    "deepeval",
    "docling",
    "fastembed",
    "gliner2",
    "graspologic_native",
    "langchain",
    "langchain_core",
    "langchain_openai",
    "langgraph",
    "neo4j",
    "openinference.instrumentation",
    "pymilvus",
    "qdrant_client",
    "sentence_transformers",
    "weaviate",
]

_CHECK = textwrap.dedent(
    """
    import importlib
    import importlib.abc
    import sys

    BLOCKED = {blocked!r}


    class BlockOptional(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            for name in BLOCKED:
                if fullname == name or fullname.startswith(name + "."):
                    message = f"No module named {{fullname!r}}"
                    raise ModuleNotFoundError(message, name=fullname)
            return None


    sys.meta_path.insert(0, BlockOptional())
    module = importlib.import_module({package!r})
    names = getattr(module, "__all__", None)
    assert names, "{package} defines no __all__"
    missing = [name for name in names if not hasattr(module, name)]
    assert not missing, f"names in __all__ that do not resolve: {{missing}}"
    """
)


@pytest.mark.parametrize("package", PACKAGES)
def test_every_exported_name_resolves_on_a_base_install(package: str) -> None:
    """Every name in ``__all__`` imports with the optional extras missing."""
    script = _CHECK.format(blocked=OPTIONAL_MODULES, package=package)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_the_agent_builder_needs_the_agents_extra() -> None:
    """``agrag.agents`` imports without the extra; ``agrag.agents.build`` does not."""
    script = _CHECK.format(blocked=OPTIONAL_MODULES, package="agrag.agents") + (
        "\ntry:\n"
        "    importlib.import_module('agrag.agents.build')\n"
        "except ModuleNotFoundError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('agrag.agents.build imported without the agents extra')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr[-2000:]
