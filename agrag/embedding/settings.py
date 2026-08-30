"""Settings for the sentence-transformers embedder."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingSettings(BaseSettings):
    """Sentence-transformers embedder configuration.

    All fields are overridable via environment variables with the
    ``EMBEDDING_`` prefix.

    Attributes:
        model: The sentence-transformers model name or path. Env: ``EMBEDDING_MODEL``.
        device: The device to load the model on, such as ``"cpu"`` or ``"cuda"``.
            ``None`` uses sentence-transformers' own default detection. Env:
            ``EMBEDDING_DEVICE``.
        normalize: Whether to L2-normalize output vectors. Env: ``EMBEDDING_NORMALIZE``.
        batch_size: The number of texts encoded per ``model.encode`` call. Env:
            ``EMBEDDING_BATCH_SIZE``.
        cache_folder: Where sentence-transformers caches downloaded models.
            ``None`` uses the library default. Env: ``EMBEDDING_CACHE_FOLDER``.
    """

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_", env_file=".env", extra="ignore"
    )

    model: str = "ibm-granite/granite-embedding-small-english-r2"
    device: str | None = None
    normalize: bool = True
    batch_size: int = 32
    cache_folder: str | None = None
