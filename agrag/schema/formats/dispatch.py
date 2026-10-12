"""Hooks that let ``load_schema`` read Pydantic classes and Turtle files."""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agrag.common.data_models.graph_schema import GraphSchema
from agrag.schema.formats.owl import load_owl
from agrag.schema.formats.pydantic_models import from_pydantic


logger = logging.getLogger(__name__)


def _is_model_class(item: Any) -> bool:
    return isinstance(item, type) and issubclass(item, BaseModel)


def is_model_source(source: Any) -> bool:
    """Return whether ``source`` is a Pydantic class or a list of them."""
    if _is_model_class(source):
        return True
    return (
        isinstance(source, (list, tuple))
        and len(source) > 0
        and all(_is_model_class(item) for item in source)
    )


def read_models(source: Any) -> GraphSchema:
    """Read a schema from a Pydantic class or a list of classes.

    The schema is named ``custom`` and has version ``1``. Each warning is
    logged. Call ``from_pydantic`` to set the name and version, or to get the
    warnings as a list.
    """
    models = [source] if _is_model_class(source) else list(source)
    result = from_pydantic(models)
    for warning in result.warnings:
        logger.warning("Schema import: %s", warning)
    return result.schema


def read_owl_file(path: Path) -> dict[str, Any]:
    """Read Turtle and return its validated canonical schema data."""
    result = load_owl(path)
    for warning in result.warnings:
        fields = (warning.code, warning.element, warning.message)
        safe_fields = tuple(
            "".join(char if char.isprintable() else " " for char in field)
            for field in fields
        )
        logger.warning("%s: %s: %s", *safe_fields)
    return result.schema.model_dump(mode="json")
