"""Configuration for the Cutover Job crash-recovery machine."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CutoverJobSettings(BaseSettings):
    """Configuration for the Cutover Job crash-recovery machine.

    Attributes:
        lease_ttl_seconds: How long a worker lease stays valid before another
            worker can take it. Env: CUTOVER_JOB_LEASE_TTL_SECONDS.

    Env prefix: ``CUTOVER_JOB_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="CUTOVER_JOB_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    lease_ttl_seconds: int = Field(default=60, gt=0)
