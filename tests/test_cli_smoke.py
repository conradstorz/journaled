from pathlib import Path
from conftest import assert_ok


def test_help_shows_usage(run_cli):
    res = run_cli("--help")
    assert_ok(res)
    assert "Usage" in res.stdout or "usage:" in res.stdout.lower()


def test_version_flag(run_cli):
    # Top-level --version flag should be passed directly
    res = run_cli("--version")
    assert res.returncode == 0
    assert any(k in res.stdout.lower() for k in ["version", "journaled"])
