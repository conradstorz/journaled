
import pytest
from pathlib import Path
from conftest import assert_ok


def test_init_db_creates_file(run_cli):
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    db = project_root / "test.db"
    res = run_cli("init-db", cwd=project_root)
    assert_ok(res)
    assert db.exists(), f"DB file was not created. STDERR:\n{res.stderr}"


def test_console_script_help(cli_bin):
    # Optional: verify the installed entry point shim works too
    import subprocess
    res = subprocess.run([str(cli_bin), "--help"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
