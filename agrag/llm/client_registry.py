"""Builds a BAML ClientRegistry from LLMClientConfig, at call time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from agrag.llm.client_config import RetryConfig


if TYPE_CHECKING:
    from agrag.llm.client_config import LLMClientConfig


# Name of the retry_policy block declared in agrag/llm/baml_src/clients.baml. BAML
# retry policies are static .baml declarations with no env-var support for their
# numeric fields, so this name's values must match RetryConfig's defaults exactly.
_DEFAULT_RETRY_POLICY_NAME = "AgragDefaultRetry"


def _retry_policy_name(retry: RetryConfig | None) -> str | None:
    """Return the BAML retry_policy name for retry, or None to attach none.

    Raises:
        ValueError: retry does not match the values declared for
            AgragDefaultRetry in .baml source. BAML retry policies are static
            declarations, so other RetryConfig values have no BAML equivalent.
    """
    if retry is None:
        return None
    if retry == RetryConfig():
        return _DEFAULT_RETRY_POLICY_NAME
    raise ValueError(
        f"retry={retry!r} has no matching BAML retry_policy. Only the default "
        f"RetryConfig() is representable, via the static "
        f"'{_DEFAULT_RETRY_POLICY_NAME}' retry_policy declared in "
        "agrag/llm/baml_src/clients.baml."
    )


def build_client_registry(
    clients: list[LLMClientConfig],
    *,
    strategy: Literal["single", "fallback", "round_robin"] = "single",
    retry: RetryConfig | None = None,
) -> object:
    """Build a ClientRegistry with the given clients, composed per strategy.

    Args:
        clients: The clients to register. Must be non-empty.
        strategy: ``"single"`` uses ``clients[0]`` directly. ``"fallback"`` and
            ``"round_robin"`` register one composite client over all of ``clients``,
            in order, and make it primary.
        retry: Retry settings to attach to every registered client. BAML retry
            policies are static ``.baml`` declarations, so only the default
            ``RetryConfig()`` values are representable; pass ``None`` to skip
            attaching a retry policy.

    Returns:
        A ClientRegistry instance. The return type is ``object`` because
        ``baml-py`` is an optional dependency (the ``llm`` extra).

    Raises:
        ValueError: ``clients`` is empty, or ``retry`` does not match the
            values declared for ``AgragDefaultRetry`` in ``.baml`` source.
        ExtractorMissingExtraError: The ``llm`` package extra is not installed.
    """
    try:
        from baml_py import ClientRegistry  # noqa: PLC0415
    except ImportError as exc:
        from agrag.ingestion.extract import ExtractorMissingExtraError  # noqa: PLC0415

        raise ExtractorMissingExtraError("build_client_registry", "llm") from exc

    if not clients:
        raise ValueError("build_client_registry needs at least one client.")

    retry_policy_name = _retry_policy_name(retry)

    registry = ClientRegistry()
    for client in clients:
        options: dict[str, object] = {"model": client.model, **client.options}
        if client.api_key is not None:
            options["api_key"] = client.api_key
        if client.base_url is not None:
            options["base_url"] = client.base_url
        registry.add_llm_client(
            name=client.name,
            provider=client.provider,
            options=options,
            retry_policy=retry_policy_name,
        )

    if strategy == "single":
        registry.set_primary(clients[0].name)
        return registry

    composite_name = "_agrag_composite"
    existing_names = {client.name for client in clients}
    while composite_name in existing_names:
        composite_name = f"{composite_name}_"
    composite_provider = "fallback" if strategy == "fallback" else "round-robin"
    registry.add_llm_client(
        name=composite_name,
        provider=composite_provider,
        options={"strategy": [client.name for client in clients]},
    )
    registry.set_primary(composite_name)
    return registry
