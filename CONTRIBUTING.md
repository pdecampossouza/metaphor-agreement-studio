# Contributing

Thank you for considering a contribution to Metaphor Agreement Studio.

## Start with an issue

For bug fixes, statistical-method changes, import-format changes, or new features, please open an issue first. Describe the research use case, expected behavior, and—when possible—a small synthetic or anonymized example. Do not attach confidential research workbooks to public issues.

## Development setup

```bash
python -m venv .venv
# activate the environment, then:
python -m pip install -r requirements-dev-release.txt
python -m pytest -q
python -m ruff check app.py src tests
```

Supported Python versions are defined in `pyproject.toml`.

## Pull requests

A pull request should:

- explain the research or software problem being addressed;
- keep methodological decisions explicit;
- include or update automated tests when behavior changes;
- preserve source-workbook immutability and missing-value semantics;
- update documentation when user-facing behavior changes;
- avoid introducing private, copyrighted, or identifiable research data.

Small documentation and configuration corrections may not need new tests. Behavioral changes should be test-driven and should pass the complete suite before review.

## Statistical contributions

When proposing a new statistical method, include a methodological reference, define the estimand/question it answers, document missing-data handling, and provide at least one reproducible validation case. New statistics must not be presented as interchangeable with agreement coefficients when they answer a different question.

## Data contributions

Only synthetic, public-domain, or explicitly redistributable example data should be committed. If a bug can only be reproduced with a private workbook, create a structurally equivalent synthetic workbook instead.

## Code style

The project uses Ruff and a line-length target of 100 characters. Favor small, testable modules and keep domain/statistical logic separate from Streamlit rendering where practical.
