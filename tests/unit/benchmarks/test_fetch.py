"""Tests the fetch step: a wrong hash is rejected and never left on disk.

Downloads use a local file URL and a patched Hugging Face client, so no network
is needed.
"""

import hashlib

import pytest

from benchmarks.datasets import fetch
from benchmarks.datasets.fetch import HashMismatchError, fetch_hf_file, fetch_url


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestFetchUrl:
    """Fetching a file over a URL with a pinned hash."""

    def test_returns_the_file_when_the_hash_matches(self, tmp_path):
        """Returns the file when the hash matches."""
        source = tmp_path / "src.txt"
        source.write_bytes(b"text")

        path = fetch_url(source.as_uri(), _sha(b"text"), tmp_path / "out" / "a.txt")

        assert path.read_bytes() == b"text"

    def test_rejects_and_deletes_a_file_with_the_wrong_hash(self, tmp_path):
        """Rejects and deletes a file with the wrong hash."""
        source = tmp_path / "src.txt"
        source.write_bytes(b"text")
        dest = tmp_path / "a.txt"

        with pytest.raises(HashMismatchError):
            fetch_url(source.as_uri(), _sha(b"other"), dest)

        assert not dest.exists()

    def test_replaces_a_cached_file_that_no_longer_matches(self, tmp_path):
        """Replaces a cached file that no longer matches."""
        source = tmp_path / "src.txt"
        source.write_bytes(b"new")
        dest = tmp_path / "a.txt"
        dest.write_bytes(b"stale")

        fetch_url(source.as_uri(), _sha(b"new"), dest)

        assert dest.read_bytes() == b"new"


class TestFetchHfFile:
    """Fetching a file from a pinned Hugging Face revision."""

    def test_rejects_a_branch_name_instead_of_a_commit(self, tmp_path):
        """Rejects a branch name instead of a commit."""
        with pytest.raises(ValueError, match="40-character"):
            fetch_hf_file("o/r", "f", revision="main", sha256="x", cache_dir=tmp_path)

    def test_checks_the_hash_of_the_downloaded_file(self, tmp_path, monkeypatch):
        """Checks the hash of the downloaded file."""
        downloaded = tmp_path / "f"
        downloaded.write_bytes(b"data")
        monkeypatch.setattr(fetch, "hf_hub_download", lambda *a, **k: str(downloaded))

        ok = fetch_hf_file("o/r", "f", revision="a" * 40, sha256=_sha(b"data"))
        assert ok == downloaded
        with pytest.raises(HashMismatchError):
            fetch_hf_file("o/r", "f", revision="a" * 40, sha256=_sha(b"x"))
