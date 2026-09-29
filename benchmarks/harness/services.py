"""Neo4j services: one compose service per corpus, so corpora never mix.

Neo4j Community holds one database per instance. The harness starts the service
of the corpus it works on and stops it afterwards, so one instance runs at a time.
"""

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from agrag.graphdb import Neo4jSettings


COMPOSE_FILE = (
    Path(__file__).resolve().parents[2] / "docker" / ("docker-compose.benchmarks.yml")
)
PASSWORD_VARIABLE = "BENCH_NEO4J_PASSWORD"


class BenchSettings(BaseSettings):
    """Benchmark harness configuration.

    Attributes:
        neo4j_password: The password of the benchmark Neo4j services, empty when
            unset. Env: ``BENCH_NEO4J_PASSWORD``.
        trace_repo: The Hugging Face dataset repo that receives the trace of a
            full run, ``None`` when unset. Env: ``BENCH_TRACE_REPO``.
    """

    model_config = SettingsConfigDict(
        env_prefix="BENCH_", env_file=".env", extra="ignore"
    )

    neo4j_password: SecretStr = SecretStr("")
    trace_repo: str | None = None


# Bolt ports on the loopback address, one per compose service. A domain adds its
# services here and in the compose file.
SERVICE_PORTS: dict[str, int] = {"fake": 7700}

CommandRunner = Callable[[Sequence[str]], None]


def run_command(command: Sequence[str]) -> None:
    """Run a command and raise on a non-zero exit.

    Args:
        command: The program and its arguments, run without a shell.

    Raises:
        subprocess.CalledProcessError: The command exits with a non-zero status.
        FileNotFoundError: The program is not installed.
    """
    subprocess.run(command, check=True)  # noqa: S603


def neo4j_settings(service: str) -> Neo4jSettings:
    """Return the connection settings of a service.

    The password comes from ``BENCH_NEO4J_PASSWORD``, in the environment or the
    repo-root ``.env``. The compose file gives the same variable to the Neo4j
    services.

    Args:
        service: The compose service name, a key of ``SERVICE_PORTS``.

    Returns:
        The bolt URI on the loopback address, the ``neo4j`` user, the password
        and the ``neo4j`` database of the service.

    Raises:
        KeyError: The service is not in ``SERVICE_PORTS``.
        RuntimeError: ``BENCH_NEO4J_PASSWORD`` is not set.
    """
    password = BenchSettings().neo4j_password.get_secret_value()
    if not password:
        raise RuntimeError(f"set {PASSWORD_VARIABLE} to the Neo4j password")
    return Neo4jSettings(
        uri=f"bolt://127.0.0.1:{SERVICE_PORTS[service]}",
        username="neo4j",
        password=SecretStr(password),
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
        """Set the compose file and the command runner, which tests replace.

        Args:
            compose_file: The compose file that defines the services.
            runner: Runs each ``docker compose`` command line.
        """
        self.compose_file = compose_file
        self._runner = runner

    def _compose(self, *args: str) -> None:
        self._runner(["docker", "compose", "-f", str(self.compose_file), *args])

    def up(self, service: str) -> None:
        """Start a service and wait until it is healthy.

        Args:
            service: The compose service name.

        Raises:
            subprocess.CalledProcessError: Compose fails or the service does not
                become healthy.
        """
        self._compose("up", "-d", "--wait", service)

    def stop(self, service: str) -> None:
        """Stop a service and keep its volume.

        Args:
            service: The compose service name.

        Raises:
            subprocess.CalledProcessError: Compose fails.
        """
        self._compose("stop", service)

    def remove(self, service: str) -> None:
        """Remove a service and its volume, which deletes the graph.

        Args:
            service: The compose service name.

        Raises:
            subprocess.CalledProcessError: Compose fails.
        """
        self._compose("down", "-v", service)
