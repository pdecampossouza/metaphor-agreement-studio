# Public-repository audit

This repository snapshot was curated from the validated local Metaphor Agreement Studio release before public publication.

## Excluded local/runtime content

The public repository intentionally excludes:

- `.venv/` and installed third-party package files;
- runtime logs and `.mas_streamlit.port`;
- local project databases and research-project folders;
- Python/test caches;
- generated research packages and exports;
- untracked user `.xlsx` / `.xlsm` files by default.

## Included example data

`imports/Teste de Concordancia - Revisor Eduardo.xlsx` is the only tracked Excel workbook in the public snapshot. It was supplied as an audited example for publication and is explicitly documented as **not a complete doctoral-study dataset**. Its SHA-256 digest is stored in `imports/source_manifest.sha256`.

## Dependency/licensing note

The public runtime does not vendor third-party Python packages. Dependencies are installed from their normal package distributions and retain their own licenses. During publication preparation, the external `krippendorff` runtime dependency was removed because the Studio already contains and tests an internal nominal coincidence-matrix implementation of Krippendorff's alpha. The public project itself is licensed under MIT.

## Verification performed before publication

- automated pytest suite passed on the curated public tree;
- Python source compilation completed successfully;
- `pyproject.toml` metadata parsed successfully;
- the example workbook opened successfully and contained no external workbook links;
- simple scans found no API keys, access tokens, private keys, passwords, runtime logs, databases, or local project state in the curated tree.

Cross-platform Ruff and pytest checks are also configured in `.github/workflows/tests.yml` and should be treated as the authoritative public CI once the repository contents are pushed.
