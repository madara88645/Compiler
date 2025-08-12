# Contributing

Thanks for your interest in contributing to Prompt Compiler App!

## Development setup
1. Python 3.10+
2. Create and activate a virtual env
3. Install deps
```
pip install -r requirements.txt
pip install -e .
```
4. Run tests
```
pytest -q
```

## Code style
- Keep functions small and typed.
- Prefer pure functions in `app/` core.
- Tests required for public behavior.

## Commit messages
Use Conventional Commits:
- feat: new feature
- fix: bug fix
- docs: documentation changes
- test: add/update tests
- chore: tooling/infra

## Pull Requests
- Link issues
- Add/adjust tests
- Update README/docs if behavior changes

## Release
- Update CHANGELOG.md
- Tag and create a GitHub Release.
