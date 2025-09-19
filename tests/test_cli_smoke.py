from pathlib import Path
from conftest import assert_ok


def test_help_shows_usage(run_cli):
    # Use uv run for CLI invocation per project rules
    import subprocess
    cmd = ["uv", "run", "src/journaled_app/cli.py", "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert_ok(res)
    assert "Usage" in res.stdout or "usage:" in res.stdout.lower()


