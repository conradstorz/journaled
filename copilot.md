update your memory to follow the rules here exactly.

The first rule is Never remove existing comments form this codebase. 
You may 'comment out' a section when it becomes un-needed but you may not remove code.
Never make a breaking change to a function without authorization.

# This file contains globally applied instructions for GitHub Copilot in this project. 
# Update as needed to guide coding style, conventions, and preferences.

- Always use type hints in Python code.
- Prefer pathlib over os.path for file operations.
- Use pytest for all new tests.
- Follow PEP8 formatting.
- Document all public functions with docstrings.
- Use environment variables for configuration, not hardcoded values.


## Additional Instructions

- Never use pip. Always use uv for package management and installation.
- Never run a Python script except as 'uv run script.py'.
- The project runs as a Docker container except during development.

---
