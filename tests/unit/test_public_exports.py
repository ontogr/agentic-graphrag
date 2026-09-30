"""Verify package imports while optional dependencies are unavailable.

Each package is imported first in a fresh interpreter, so a circular import between
subpackages fails here instead of depending on which module a caller imports first.
Optional dependencies are blocked with an import hook that raises
``ModuleNotFoundError``, which is what a base install without extras does.
The lazy agent builder is tested separately because it requires an optional extra.
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

OPTIONAL_EXPORTS = {
    "agrag.agents": {"build_agent"},
}

_CHECK = textwrap.dedent(
    """
    import importlib
    import importlib.abc
    import sys

    BLOCKED = {blocked!r}
    OPTIONAL_EXPORTS = {optional_exports!r}


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
    missing = [
        name
        for name in names
        if name not in OPTIONAL_EXPORTS and not hasattr(module, name)
    ]
    assert not missing, f"names in __all__ that do not resolve: {{missing}}"
    """
)


@pytest.mark.parametrize("package", PACKAGES)
def test_every_required_export_resolves_on_a_base_install(package: str) -> None:
    """Every non-optional name in ``__all__`` resolves with the extras missing."""
    script = _CHECK.format(
        blocked=OPTIONAL_MODULES,
        package=package,
        optional_exports=OPTIONAL_EXPORTS.get(package, set()),
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_the_agent_builder_needs_the_agents_extra() -> None:
    """The lazy package-level builder import requires the optional extra."""
    script = _CHECK.format(
        blocked=OPTIONAL_MODULES,
        package="agrag.agents",
        optional_exports=OPTIONAL_EXPORTS["agrag.agents"],
    ) + (
        "\ntry:\n"
        "    from agrag.agents import build_agent\n"
        "except ModuleNotFoundError as error:\n"
        "    assert error.name in BLOCKED\n"
        "else:\n"
        "    raise SystemExit('builder imported without the agents extra')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr[-2000:]
