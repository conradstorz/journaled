
import pytest
from pathlib import Path
from conftest import assert_ok


def test_init_db_creates_file(run_cli):
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    db = project_root / "test.db"
    # Use uv run for CLI invocation per project rules
    import subprocess
    cmd = ["uv", "run", "src/journaled_app/cli.py", "init-db", "--db", str(db)]
    res = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
    assert res is not None, "Subprocess result is None. CLI may have failed to launch."
    assert_ok(res)
    if not db.exists():
        print(f"DB file not found at {db}. Subprocess stdout: {res.stdout}, stderr: {res.stderr}")
    assert db.exists(), f"DB file was not created. STDERR:\n{res.stderr}"


def test_console_script_help():
    # Run CLI help using Python module directly
    import subprocess
    import sys
    import os
    src_path = str(Path(__file__).parent.parent / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")
    res = subprocess.run([
        sys.executable, "-m", "journaled_app.cli", "--help"
    ], env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
