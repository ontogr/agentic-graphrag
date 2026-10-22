"""Validation shared by external vector store settings."""

from typing import Annotated

from pydantic import StringConstraints


CollectionPrefix = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,40}$")
]
