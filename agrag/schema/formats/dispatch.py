"""Internal dispatch helpers for schema format imports."""

import logging
from pathlib import Path
from typing import Any

from agrag.schema.formats.owl import load_owl


logger = logging.getLogger("agrag.schema.formats.dispatch")


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
