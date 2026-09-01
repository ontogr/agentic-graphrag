"""Shared setup for agent unit tests."""

import os


# langchain-openai probes an AF_INET socket when computing default TCP
# keepalive options during ChatOpenAI construction. Under pytest-socket's
# --disable-socket guard the probe raises SocketBlockedError, which
# pytest-socket re-warns as a UserWarning and pollutes unit-test output.
# The library's documented kill-switch skips the probe entirely. Unit
# tests never open real connections, so the keepalive defaults are
# irrelevant here. Integration tests are unaffected (separate tree).
os.environ.setdefault("LANGCHAIN_OPENAI_TCP_KEEPALIVE", "0")
