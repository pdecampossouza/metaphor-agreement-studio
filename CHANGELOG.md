# Changelog

All notable public changes to Metaphor Agreement Studio will be documented here.

The project follows semantic-versioning principles for public releases. Internal phase builds preceded the first public repository snapshot.

## 1.0.0 - 2026-09-11

First public research-software release.

### Added
- Assisted Excel discovery and validation for text-, binary-, and fill-color encoded metaphor annotations.
- Human-confirmed annotation mappings and grammatical-category normalization.
- Explicit worksheet roles for study, synthetic/example, and ignored data.
- Occurrence-aware lexical-unit identity, aggregate-source safeguards, and conservative new-rater alignment.
- No-reference, reference-rater, and expert-benchmark analysis perspectives.
- Observed agreement, Cohen's Kappa, Fleiss' Kappa, class-specific agreement, Krippendorff's alpha, Cochran's Q, McNemar comparisons, and multiplicity correction.
- Fisher-Freeman-Halton exact analysis of grammatical-category association, including the choice to include all categories or exclude categories with fewer than five occurrences.
- Linked agreement, disagreement, category, source, rater, statistical, and annotation workspaces.
- Human-readable rater names throughout interactive and publication figures.
- Explicit `Disagreement cases` terminology for units with inter-rater disagreement.
- Report-specific rater selection with complete recalculation of the report analytical scope.
- Multi-page comparison PDF, publication figures, Excel/CSV exports, LaTeX helpers, provenance hashes, and reproducibility metadata.
- Persistent research projects, dataset/analysis versioning, audit history, portable backups, and immutable source copies.
- Windows and macOS local launchers.
- Automated tests and public cross-platform CI configuration.

### Research safeguards
- Source workbooks are never modified.
- Missing annotations never become non-metaphor by default.
- Uncertain mappings and probable rater matches require explicit human confirmation.
- Aggregate sources are excluded from default overall totals after confirmation.
- Reference-rater status does not imply ground truth.
- Expert-benchmark interpretation is activated only by an explicit researcher choice.
