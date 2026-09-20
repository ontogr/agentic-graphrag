"""Process-global DeepAgents harness profile registration.

Registers, once per process and per provider, the profile that trims
DeepAgents' generic tool surface for this project's agent: the execute
tool is excluded and the general-purpose subagent is disabled. The
registration is a process-global side effect, so it is guarded against
re-registration.
"""

from collections.abc import Mapping
from typing import Any


_HARNESS_PROFILE_REGISTERED: set[str] = set()


def model_provider_key(model: Any, *, fallback: str) -> str:
    """Return the provider key DeepAgents resolves a profile by.

    DeepAgents looks a pre-built model up by the provider its own
    ``_get_ls_params`` reports, which is not always the provider name
    this package configured: ``openai-generic`` builds a
    ``ChatOpenAI``, which reports ``openai``. Registering the
    configured name alone would miss, so read the built model and
    fall back to the configured name when it says nothing usable.

    Args:
        model: The built chat model the agent calls.
        fallback: The configured provider name, used when the model
            reports no provider.

    Returns:
        The resolved provider key, or the fallback.
    """
    params_getter = getattr(model, "_get_ls_params", None)
    if callable(params_getter):
        try:
            params = params_getter()
        except (AttributeError, TypeError, NotImplementedError):
            params = None
        if isinstance(params, Mapping):
            provider = params.get("ls_provider")
            if provider:
                return str(provider)
    return fallback


def ensure_harness_profile(provider: str) -> None:
    """Register the harness profile for provider, once per process.

    Args:
        provider: The provider key DeepAgents resolves profiles by,
            either a provider string such as ``"anthropic"`` or an
            exact ``"provider:model"`` string.
    """
    if provider in _HARNESS_PROFILE_REGISTERED:
        return
    from deepagents import (  # noqa: PLC0415
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        register_harness_profile,
    )

    register_harness_profile(
        provider,
        HarnessProfile(
            excluded_tools=frozenset({"execute"}),
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    _HARNESS_PROFILE_REGISTERED.add(provider)
