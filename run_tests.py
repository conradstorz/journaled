"""
run_tests.py

A script to run pytest on the CLI integration tests with maximum output suppression for SQLAlchemy and warnings.
- Sets environment variables to silence SQLAlchemy warnings.
- Configures pytest to run in quiet mode, suppress warnings, and minimize traceback output.
- Uses subprocess to invoke pytest as a separate process.
- Prints a summary of the test result.
"""

import os
import subprocess
import sys

def main():
    # Set environment variables to suppress SQLAlchemy warnings
    env = os.environ.copy()
    # This silences the SQLAlchemy 'Uber warning' (if present)
    env['SQLALCHEMY_SILENCE_UBER_WARNING'] = '1'

    # Build the pytest command
    pytest_cmd = [
        'pytest',
        '-q',                # Quiet mode: minimal output
        '-p', 'no:warnings', # Suppress all warnings
        '--tb=line',         # One-line tracebacks for errors/failures
        '--show-capture=no', # Do not show captured stdout/stderr, even on failure
        '--maxfail=1',       # Stop after first failure
    ]

    with open("test_run.txt", "w") as f:
        f.write("Running CLI integration tests with suppressed SQLAlchemy and warning output...\n")
        f.write(f"Command: {' '.join(pytest_cmd)}\n\n")
        result = subprocess.run(
            pytest_cmd,
            env=env,
            text=True,
            stdout=f,
            stderr=subprocess.STDOUT
        )
        # Write a summary of the result
        if result.returncode == 0:
            f.write("\nAll tests passed! ✅\n")
        else:
            f.write(f"\nSome tests failed. Exit code: {result.returncode}\n")
            sys.exit(result.returncode)

if __name__ == "__main__":
    main()
