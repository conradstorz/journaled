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
        'tests/test_cli_integration.py'  # Only run the CLI integration test file
    ]

    print("Running CLI integration tests with suppressed SQLAlchemy and warning output...")
    print(f"Command: {' '.join(pytest_cmd)}\n")

    # Run pytest as a subprocess
    result = subprocess.run(
        pytest_cmd,
        env=env,
        text=True
    )

    # Print a summary of the result
    if result.returncode == 0:
        print("\nAll tests passed! ✅")
    else:
        print(f"\nSome tests failed. Exit code: {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
