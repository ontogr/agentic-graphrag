"""Process-global DeepAgents harness profile registration.

Registers, once per process and per provider, the profile that trims
DeepAgents' generic tool surface for this project's agent: the execute
tool is excluded and the general-purpose subagent is disabled. The
registration is a process-global side effect, so it is guarded against
re-registration.
"""

_HARNESS_PROFILE_REGISTERED: set[str] = set()
_AGENT_PROVIDER_TO_HARNESS_KEY = {
    "anthropic": "anthropic",
    "openai": "openai",
    "openai-generic": "openai",
    "google-ai": "google_genai",
}


def model_provider_key(provider: str) -> str:
    """Return the DeepAgents provider key for a configured agent provider.

    Args:
        provider: The configured agent provider.

    Returns:
        The provider key used by DeepAgents harness profiles.
    """
    return _AGENT_PROVIDER_TO_HARNESS_KEY[provider]


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
