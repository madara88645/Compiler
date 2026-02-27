# CLCD (Component Lifecycle Dependency Checker)

This repository includes an automated CLCD check to detect dependency lifecycle drift across Python and web components.

## Local usage

```bash
python scripts/clcd_check.py
```

The checker reports:

- Dependency declaration drift between `pyproject.toml` and `requirements.txt`
- Missing installed Python dependencies from `pip freeze`
- npm dependency tree health from `npm ls --all --json`
- Overlap between `dependencies` and `devDependencies`

The output is a markdown table with severity and recommended fixes. The command exits with status code `1` when issues are found so CI can fail fast.

## CI integration

GitHub Actions workflow: `.github/workflows/clcd.yml`.

The workflow:

1. Installs Python and Node dependencies.
2. Runs `python scripts/clcd_check.py`.
3. Fails the job when CLCD issues are detected.
