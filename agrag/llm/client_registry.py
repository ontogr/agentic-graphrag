"""Builds a BAML ClientRegistry from LLMClientConfig, at call time."""

from typing import Literal

from baml_py import ClientRegistry

from agrag.llm.client_config import LLMClientConfig


def build_client_registry(
    clients: list[LLMClientConfig],
    *,
    strategy: Literal["single", "fallback", "round_robin"] = "single",
) -> ClientRegistry:
    """Build a ClientRegistry with the given clients, composed per strategy.

    Args:
        clients: The clients to register. Must be non-empty.
        strategy: ``"single"`` uses ``clients[0]`` directly. ``"fallback"`` and
            ``"round_robin"`` register one composite client over all of ``clients``,
            in order, and make it primary.

    Returns:
        A registry ready to pass as ``{"client_registry": registry}`` to a BAML
        function call.

    Raises:
        ValueError: ``clients`` is empty.
    """
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
    composite_provider = "fallback" if strategy == "fallback" else "round-robin"
    registry.add_llm_client(
        name=composite_name,
        provider=composite_provider,
        options={"strategy": [client.name for client in clients]},
    )
    registry.set_primary(composite_name)
    return registry
