"""Trusted settings for the local MCP server.

Scope comes from these settings only. No tool argument can widen it.
"""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpServerSettings(BaseSettings):
    """Scope and output limits of the MCP server.

    The server refuses to start with an empty scope, because an empty scope
    would otherwise read as no restriction in the caller's mind.

    Attributes:
        scope_document_keys: Comma-separated keys of the documents the server
            may read. Env: ``AGRAG_MCP_SCOPE_DOCUMENT_KEYS``.
        max_hits: The most hits one search returns. Env: ``AGRAG_MCP_MAX_HITS``.
        max_snippet_chars: The most characters of a hit snippet. Env:
            ``AGRAG_MCP_MAX_SNIPPET_CHARS``.
        max_fetch_chars: The most characters returned for each fetched id. Env:
            ``AGRAG_MCP_MAX_FETCH_CHARS``.
        max_fetch_ids: The most evidence ids one fetch or citation check takes.
            Env: ``AGRAG_MCP_MAX_FETCH_IDS``.
        max_response_chars: The most characters of one serialized result. The
            limit counts the text and structured copies that the SDK sends, so
            each result is measured at twice its JSON length. Env:
            ``AGRAG_MCP_MAX_RESPONSE_CHARS``.
        request_deadline_seconds: The server-side timeout of each store read.
            Env: ``AGRAG_MCP_REQUEST_DEADLINE_SECONDS``.

    Raises:
        ValueError: ``scope_document_keys`` names no document key.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGRAG_MCP_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    scope_document_keys: str = ""
    max_hits: int = Field(default=10, ge=1)
    max_snippet_chars: int = Field(default=240, ge=1)
    max_fetch_chars: int = Field(default=4000, ge=1)
    max_fetch_ids: int = Field(default=20, ge=1)
    max_response_chars: int = Field(default=60000, ge=1)
    request_deadline_seconds: float = Field(default=30.0, gt=0)

    @model_validator(mode="after")
    def _require_scope(self) -> "McpServerSettings":
        """Reject a scope that names no document key."""
        if not self.scope:
            raise ValueError("scope_document_keys must list at least one document key")
        return self

    @property
    def scope(self) -> frozenset[str]:
        """The document keys in scope, without blank entries or surrounding spaces."""
        return frozenset(
            key.strip() for key in self.scope_document_keys.split(",") if key.strip()
        )
