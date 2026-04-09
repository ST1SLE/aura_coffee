## ADDED Requirements

### Requirement: Shared package structure
The `packages/shared/` directory SHALL be a valid Python package with `pyproject.toml` (PEP 621), exposing the `shared` module. It SHALL be installable via `pip install -e .` and importable as `import shared` by all backend services.

#### Scenario: Install shared package
- **WHEN** a developer runs `pip install -e .` in `packages/shared/`
- **THEN** the package installs without errors and `import shared` succeeds in Python

#### Scenario: Shared package contains base exports
- **WHEN** `shared` is imported
- **THEN** it SHALL expose a `__version__` string and an empty `shared.models` submodule

### Requirement: Service package structure
Each backend service (`services/core-api/`, `services/payment-worker/`, `services/sms-worker/`) SHALL be a valid Python package with its own `pyproject.toml`, declaring `shared` as a dependency.

#### Scenario: Install service package
- **WHEN** a developer runs `pip install -e ".[dev]"` in any service directory
- **THEN** the package and its dev dependencies (pytest, httpx, ruff) install without errors

### Requirement: Root-level ruff configuration
A root-level `pyproject.toml` SHALL configure `ruff` with shared lint and format rules. All Python code in the monorepo SHALL pass `ruff check` and `ruff format --check` with zero violations.

#### Scenario: Lint clean codebase
- **WHEN** a developer runs `ruff check .` and `ruff format --check .` from the repo root
- **THEN** both commands exit with code 0

### Requirement: Pytest configuration
Each backend service SHALL include a `pytest.ini` or `pyproject.toml` `[tool.pytest]` section. Running `pytest` in a service directory SHALL discover and run tests from its `tests/` directory.

#### Scenario: Run tests in core-api
- **WHEN** a developer runs `pytest` in `services/core-api/`
- **THEN** pytest discovers tests in `services/core-api/tests/` and executes them
