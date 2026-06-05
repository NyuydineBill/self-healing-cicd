# Contributing

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
