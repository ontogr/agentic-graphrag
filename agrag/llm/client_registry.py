"""Builds a BAML ClientRegistry from LLMClientConfig, at call time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal


if TYPE_CHECKING:
    from agrag.llm.client_config import LLMClientConfig


def build_client_registry(
    clients: list[LLMClientConfig],
    *,
    strategy: Literal["single", "fallback", "round_robin"] = "single",
) -> object:
    """Build a ClientRegistry with the given clients, composed per strategy.

    Args:
        clients: The clients to register. Must be non-empty.
        strategy: ``"single"`` uses ``clients[0]`` directly. ``"fallback"`` and
            ``"round_robin"`` register one composite client over all of ``clients``,
            in order, and make it primary.

    Returns:
        A ClientRegistry instance. The return type is ``object`` because
        ``baml-py`` is an optional dependency (the ``llm`` extra).

    Raises:
        ValueError: ``clients`` is empty.
        ExtractorMissingExtraError: The ``llm`` package extra is not installed.
    """
    try:
        from baml_py import ClientRegistry  # noqa: PLC0415
    except ImportError as exc:
        from agrag.ingestion.extract import ExtractorMissingExtraError  # noqa: PLC0415

        raise ExtractorMissingExtraError("build_client_registry", "llm") from exc

    if not clients:
        raise ValueError("build_client_registry needs at least one client.")

    registry = ClientRegistry()
    for client in clients:
        options: dict[str, object] = {"model": client.model, **client.options}
        if client.api_key is not None:
            options["api_key"] = client.api_key
        if client.base_url is not None:
            options["base_url"] = client.base_url
        registry.add_llm_client(
            name=client.name, provider=client.provider, options=options
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
