# Release 1.0.0 Acceptance Evidence

This public release checklist maps the core research-software requirements to automated or reproducible evidence in the repository.

1. **Discover and inspect an example workbook without modifying it** — `tests/e2e/test_real_eduardo_workbook.py`, `tests/test_source_immutability.py`.
2. **Require human validation before analysis** — import/validation tests under `tests/import_engine/` and `tests/validation/`.
3. **Preserve missing values and canonical lexical-unit identity** — domain, validation, and statistics tests.
4. **Support text/color annotation evidence and explicit mapping confirmation** — import-engine mapping/color tests.
5. **Prevent aggregate-source double counting** — aggregate validation and real-workbook regressions.
6. **Compute pairwise observed agreement and Cohen's Kappa** — `tests/statistics/` and end-to-end example regression.
7. **Support multi-rater Fleiss' Kappa and Krippendorff's nominal alpha** — multi-rater statistics tests.
8. **Keep classification tendency separate from agreement** — Cochran's Q / McNemar tests and reporting regressions.
9. **Support Fisher-Freeman-Halton grammatical-category association** — `tests/statistics/test_category_association.py` and PDF/UI tests.
10. **Support no-reference, reference-rater, and expert-benchmark perspectives** — statistical and rater-explorer tests.
11. **Connect statistical summaries to disagreement/audit views** — review and UI tests.
12. **Generate publication-oriented figures with human-readable rater labels** — figure data/rendering tests.
13. **Generate a reproducible comparison PDF for a selected rater scope** — reporting and Statistical Analysis UI tests.
14. **Persist research projects, versions, immutable source copies, and backups** — persistence and end-to-end project tests.
15. **Export validated data, results, and reproducibility metadata** — export package/workbook/manifest tests.

## Public distribution checks

- `README.md`, `LICENSE`, `CITATION.cff`, `CONTRIBUTING.md`, support/security guidance, and public methodology documentation are present.
- GitHub Actions runs pytest and Ruff across Python 3.11-3.13 on Linux, Windows, and macOS.
- The distributed `imports/Teste de Concordancia - Revisor Eduardo.xlsx` is an audited example, not a complete doctoral-study dataset.
- Private/local workbooks are ignored by default.
- Local `.venv`, runtime logs, project databases, caches, and Streamlit port files are excluded from version control.
- The public runtime does not require the external `krippendorff` package; nominal alpha uses the tested internal coincidence-matrix implementation.
