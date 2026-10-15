"""Trusted settings for the local MCP server.

Scope comes from these settings only. No tool argument can widen it.
"""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpServerSettings(BaseSettings):
    """Scope and output limits of the MCP server.

    The server refuses to start with an empty scope, because an empty scope
    would otherwise read as no restriction in the caller's mind. It starts
    read-only; write access also requires a project id and agent id.

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
        project_id: Trusted project scope for task and decision operations. Env:
            ``AGRAG_MCP_PROJECT_ID``.
        agent_id: Trusted author for task and decision writes. Env:
            ``AGRAG_MCP_AGENT_ID``.
        read_only: Whether the server omits and blocks all write tools. Env:
            ``AGRAG_MCP_READ_ONLY``.
        allow_reject: Whether ``reject_decision`` is registered. Env:
            ``AGRAG_MCP_ALLOW_REJECT``.

    Raises:
        ValueError: The document scope is empty, or write access lacks either
            trusted identity.
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
    max_response_chars: int = Field(default=100000, ge=1)
    request_deadline_seconds: float = Field(default=30.0, gt=0)
    project_id: str = ""
    agent_id: str = ""
    read_only: bool = True
    allow_reject: bool = False

    @model_validator(mode="after")
    def _require_scope(self) -> "McpServerSettings":
        """Reject a scope that names no document key."""
        if not self.scope:
            raise ValueError("scope_document_keys must list at least one document key")
        if not self.read_only and (
            not self.project_id.strip() or not self.agent_id.strip()
        ):
            raise ValueError("project_id and agent_id must not be blank")
        return self

    @property
    def scope(self) -> frozenset[str]:
        """The document keys in scope, without blank entries or surrounding spaces."""
        return frozenset(
            key.strip() for key in self.scope_document_keys.split(",") if key.strip()
        )
