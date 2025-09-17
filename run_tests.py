"""
run_tests.py

A script to run pytest on the CLI integration tests with maximum output suppression for SQLAlchemy and warnings.
- Sets environment variables to silence SQLAlchemy warnings.
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
        '--tb=line',         # One-line tracebacks for errors/failures
        '--maxfail=1',       # Stop after first failure
        '--capture=no',      # Show all print output
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
            f.write("\nAll tests passed!\n")
        else:
            f.write(f"\nSome tests failed. Exit code: {result.returncode}\n")
            # Print last 40 lines of test_run.txt to console for traceability
            f.flush()
            with open("test_run.txt", "r") as fr:
                lines = fr.readlines()
                print("\n--- Last 40 lines of test_run.txt ---")
                for line in lines[-40:]:
                    print(line.rstrip())
            sys.exit(result.returncode)
    print("Run ended. Pytest output is available in test_run.txt")

if __name__ == "__main__":
    main()
