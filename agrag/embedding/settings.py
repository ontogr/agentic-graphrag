"""Settings for the dense embedders."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingSettings(BaseSettings):
    """Configuration shared by the FastEmbed and sentence-transformers embedders.

    All fields accept overrides through environment variables with the
    ``EMBEDDING_`` prefix.

    Attributes:
        model: The model name. The FastEmbed embedder takes a model that FastEmbed
            supports. The sentence-transformers embedder takes a model name or
            path. Env: ``EMBEDDING_MODEL``.
        device: The device to load the model on, such as ``"cpu"`` or ``"cuda"``.
            Only the sentence-transformers embedder uses it, and ``None`` uses its
            own default detection. The FastEmbed embedder ignores it. Env:
            ``EMBEDDING_DEVICE``.
        normalize: Whether to L2-normalize output vectors. Env: ``EMBEDDING_NORMALIZE``.
        batch_size: The number of texts encoded per model call. Env:
            ``EMBEDDING_BATCH_SIZE``.
        cache_folder: Where the model files are cached. ``None`` uses the library
            default. Env: ``EMBEDDING_CACHE_FOLDER``.
    """

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    model: str = "ibm-granite/granite-embedding-small-english-r2"
    device: str | None = None
    normalize: bool = True
    batch_size: int = 32
    cache_folder: str | None = None
