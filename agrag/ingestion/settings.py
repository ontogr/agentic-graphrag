"""Configuration for the Cutover Job crash-recovery machine."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class CutoverJobSettings(BaseSettings):
    """Configuration for the Cutover Job crash-recovery machine.

    Attributes:
        lease_ttl_seconds: How long a worker's lease is valid before another
            worker may steal it. Env: CUTOVER_JOB_LEASE_TTL_SECONDS.

    Env prefix: ``CUTOVER_JOB_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="CUTOVER_JOB_", env_file=".env", extra="ignore"
    )

    lease_ttl_seconds: int = 60
