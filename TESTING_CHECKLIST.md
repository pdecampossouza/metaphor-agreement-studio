# Metaphor Agreement Studio 1.0.0 — Public Release Checklist

## Start and stop

- [ ] Windows: `START_METAPHOR_STUDIO_WINDOWS.bat` creates/updates the local environment and opens the app.
- [ ] Windows: `STOP_METAPHOR_STUDIO_WINDOWS.bat` stops it.
- [ ] macOS: `Metaphor Agreement Studio.app` or `START_METAPHOR_STUDIO_MAC.command` opens the app.
- [ ] macOS: `STOP_METAPHOR_STUDIO_MAC.command` stops it.

## Audited example workbook

- [ ] Overview detects `imports/Teste de Concordancia - Revisor Eduardo.xlsx` without silently validating it.
- [ ] Data Validation detects the expected source tables and rater columns.
- [ ] Category normalization and aggregate-source decisions remain explicit researcher decisions.
- [ ] Validation yields the expected analytical lexical-unit scope.
- [ ] The original workbook hash/bytes are unchanged after inspection, validation, analysis, project save, and export.

## Analysis

- [ ] No reference / Reference rater / Expert benchmark can be switched without changing source annotations.
- [ ] Pairwise observed agreement and Cohen's Kappa are available.
- [ ] For 3+ selected raters, Fleiss' Kappa and complementary Krippendorff's alpha are available.
- [ ] Cochran's Q is labelled as a classification-tendency test, not an agreement coefficient.
- [ ] Grammatical Category Association offers both `Exclude categories with fewer than 5 occurrences` and `Include all grammatical categories`.
- [ ] Fisher-Freeman-Halton results record exact p-values and the configured multiple-testing correction.
- [ ] Comparison Report allows explicit rater selection and recalculates the PDF using only the selected raters.

## Figures and reporting

- [ ] Figures display rater names rather than internal `rater_...` identifiers.
- [ ] Figure terminology uses `Disagreement cases` / `Disagreement Density Map` rather than ambiguous `Review cases` labels.
- [ ] Interactive and Publication views render successfully.
- [ ] Publication PDF/SVG/PNG exports preserve chart aspect ratio.
- [ ] `View validated annotations` opens the traceability matrix without an attribute error.
- [ ] Comparison Report includes methodology, selected analytical scope, statistical results, disagreement cases, and reproducibility metadata.

## Projects and exports

- [ ] A Quick Analysis can be saved as a Research Project, closed, and reopened.
- [ ] Dataset and analysis versions are visible in project history.
- [ ] Portable `.masproject.zip` backup can be created and restored.
- [ ] Export Center creates validated data, structured results, figures, and a reproducibility manifest.

## Developer verification

```bash
python -m pytest -q
python -m ruff check app.py src tests
```

On Windows, `RUN_RELEASE_TESTS_WINDOWS.bat` runs the same release verification after the environment has been created once.
