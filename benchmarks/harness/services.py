"""Neo4j services: one compose service per corpus, so corpora never mix.

Neo4j Community holds one database per instance. The harness starts the service
of the corpus it works on and stops it afterwards, so one instance runs at a time.
"""

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import SecretStr

from agrag.graphdb import Neo4jSettings


COMPOSE_FILE = (
    Path(__file__).resolve().parents[2] / "docker" / ("docker-compose.benchmarks.yml")
)
PASSWORD = "benchmark-local"

# Bolt ports on the loopback address, one per compose service. A domain adds its
# services here and in the compose file.
SERVICE_PORTS: dict[str, int] = {"fake": 7700}

CommandRunner = Callable[[Sequence[str]], None]


def run_command(command: Sequence[str]) -> None:
    """Run a command and raise on a non-zero exit."""
    subprocess.run(command, check=True)  # noqa: S603


def neo4j_settings(service: str) -> Neo4jSettings:
    """Return the connection settings of a service.

    Raises:
        KeyError: The service is not in ``SERVICE_PORTS``.
    """
    return Neo4jSettings(
        uri=f"bolt://127.0.0.1:{SERVICE_PORTS[service]}",
        username="neo4j",
        password=SecretStr(PASSWORD),
        database="neo4j",
    )


class Services:
    """Starts, stops and removes benchmark Neo4j services through docker compose.

    Attributes:
        compose_file: The compose file that defines the services.
    """

    def __init__(
        self,
        compose_file: Path = COMPOSE_FILE,
        runner: CommandRunner = run_command,
    ) -> None:
        """Set the compose file and the command runner, which tests replace."""
        self.compose_file = compose_file
        self._runner = runner

    def _compose(self, *args: str) -> None:
        self._runner(["docker", "compose", "-f", str(self.compose_file), *args])

    def up(self, service: str) -> None:
        """Start a service and wait until it is healthy."""
        self._compose("up", "-d", "--wait", service)

    def stop(self, service: str) -> None:
        """Stop a service and keep its volume."""
        self._compose("stop", service)

    def remove(self, service: str) -> None:
        """Remove a service and its volume, which deletes the graph."""
        self._compose("down", "-v", service)
