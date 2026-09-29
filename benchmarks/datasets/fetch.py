"""Fetch source files at a pinned revision and check their hashes.

Fixtures hold IDs and hashes, never source text. Every byte of source text comes
through here at run time and is checked against the fixture.
"""

import hashlib
import urllib.request
from pathlib import Path

from huggingface_hub import hf_hub_download

from benchmarks.harness.record import REPO_ROOT


CACHE_DIR = REPO_ROOT / "reports" / "benchmarks" / "data"


class HashMismatchError(Exception):
    """A fetched file does not match the hash the fixture pins."""


def _verify(path: Path, sha256: str) -> None:
    """Raise when the file at ``path`` has a different hash."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != sha256:
        raise HashMismatchError(f"{path.name}: expected {sha256}, got {digest}")


def fetch_url(url: str, sha256: str, dest: Path) -> Path:
    """Download a file over HTTP and check its hash.

    A file already at ``dest`` with the right hash is reused.

    Args:
        url: The file URL.
        sha256: The expected SHA-256.
        dest: Where to keep the file.

    Raises:
        HashMismatchError: The bytes differ from ``sha256``. The file is deleted.
    """
    if dest.exists():
        try:
            _verify(dest, sha256)
        except HashMismatchError:
            dest.unlink()
        else:
            return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response:  # noqa: S310
        dest.write_bytes(response.read())
    try:
        _verify(dest, sha256)
    except HashMismatchError:
        dest.unlink()
        raise
    return dest


def fetch_hf_file(
    repo: str,
    filename: str,
    *,
    revision: str,
    sha256: str,
    repo_type: str = "dataset",
    cache_dir: Path = CACHE_DIR,
) -> Path:
    """Download a file from a Hugging Face repo at a pinned revision.

    Args:
        repo: The repo id.
        filename: The path of the file in the repo.
        revision: The commit hash. A branch name is not accepted, because it
            can move.
        sha256: The expected SHA-256.
        repo_type: ``dataset``, ``model`` or ``space``.
        cache_dir: Where downloads go.

    Raises:
        HashMismatchError: The bytes differ from ``sha256``.
        ValueError: ``revision`` is not a 40-character commit hash.
    """
    if len(revision) != 40:
        raise ValueError("revision must be a full 40-character commit hash")
    path = Path(
        hf_hub_download(
            repo,
            filename,
            revision=revision,
            repo_type=repo_type,
            cache_dir=cache_dir / "hf",
        )
    )
    _verify(path, sha256)
    return path
