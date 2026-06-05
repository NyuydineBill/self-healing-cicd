# Contributing

## Installation

**From PyPI (recommended for users):**
```bash
pip install self-healing-cicd
self-heal check
```

**As a GitHub Action (CI integration):**
```yaml
- uses: NyuydineBill/self-healing-cicd@v0.1.0
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    openai-api-key: ${{ secrets.OPENAI_API_KEY }}
```

## Development Setup

```bash
git clone https://github.com/NyuydineBill/self-healing-cicd.git
cd self-healing-cicd
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"          # installs dev extras from pyproject.toml
pre-commit install               # wire up git hooks
cp .env.example .env             # fill in your tokens
```

## Running Tests

```bash
pytest                           # runs tests/ with coverage
pytest -k test_orchestrator      # single module
pytest --no-cov                  # skip coverage for a quick run
```

## Linting & Type Checking

```bash
ruff check .                     # lint
ruff format .                    # format
mypy agents/ config/ orchestrator/ parsers/ utils/ main.py
```

These same checks run in CI on every push. Fix any errors before opening a PR.

## Adding a New Language Parser

1. Create `parsers/<language>_parser.py` implementing `BaseLogParser` from [parsers/base.py](parsers/base.py).
2. Register it in [parsers/registry.py](parsers/registry.py).
3. Add tests in `tests/test_parsers.py`.
4. Document it in `sample_projects/README.md` with a failure example.

## Adding a New Agent

1. Create `agents/<name>_agent.py`.
2. Add it to [agents/__init__.py](agents/__init__.py).
3. Wire it into [orchestrator/workflow.py](orchestrator/workflow.py).
4. Add unit tests covering the happy path and at least one error path.

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR.
- Include tests for new behaviour.
- Update `.env.example` if you add new environment variables.
- Run `pytest` and `ruff check .` locally before pushing.
- Self-heal branches (`self-heal/*`) are bot-generated — do not edit them manually.

## Commit Style

Use conventional commits:

```
feat: add Go log parser
fix: handle empty log zip gracefully
docs: update .env.example with new settings
chore: bump openai to 2.x
```

## Releasing a New Version

1. Update `version` in [pyproject.toml](pyproject.toml).
2. Commit: `git commit -m "chore: bump version to vX.Y.Z"`
3. Push: `git push origin main`
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`

The [publish workflow](.github/workflows/publish.yml) runs automatically:
- Runs the full test suite (publish is blocked on failure)
- Builds wheel + sdist
- Publishes to [PyPI](https://pypi.org/project/self-healing-cicd) via OIDC (no token needed)
- Creates a GitHub Release with auto-generated notes and dist files attached

## Action inputs reference

See [action.yml](action.yml) for the full list of inputs and defaults.
Key CI-safe defaults set automatically: `REQUIRE_APPROVAL=false`, `AUTO_APPROVE_PATCHES=true`.
