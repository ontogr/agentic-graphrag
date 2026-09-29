"""Tests the command-line argument checks of ``python -m benchmarks``."""

import pytest

from benchmarks.__main__ import main


class TestMain:
    """Argument validation happens before any run starts."""

    @pytest.mark.parametrize("value", ["0", "-1"])
    def test_rejects_non_positive_concurrency(self, value, capsys):
        """Rejects a concurrency that would leave every task waiting."""
        with pytest.raises(SystemExit) as exit_info:
            main(["run", "fake", "--mode", "lite", "--concurrency", value])

        assert exit_info.value.code == 2
        assert "--concurrency" in capsys.readouterr().err
