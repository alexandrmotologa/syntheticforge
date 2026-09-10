# Contributing to SyntheticForge

Thank you for your interest in improving SyntheticForge. Contributions are welcome.

## Development setup

SyntheticForge requires Python 3.12+ and `uv` for package management.

1. Clone the repository:
   ```bash
   git clone https://github.com/alexandrmotologa/syntheticforge.git
   cd syntheticforge
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv sync --all-extras
   ```

3. Run the test suite:
   ```bash
   uv run pytest
   ```

4. Format and lint the codebase:
   ```bash
   uv run ruff check --fix
   uv run ruff format
   ```

## Pull request guidelines

- Add unit tests for new generators, graph algorithms, or streaming sinks.
- Ensure all tests pass with `uv run pytest`.
- Keep documentation up to date with schema changes or new CLI options.
- Use Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
