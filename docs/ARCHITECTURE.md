# Architecture

Metaphor Agreement Studio is a local Streamlit application with a deliberately separated research core.

## Layers

- `import_engine/`: workbook inspection, table discovery, annotation evidence, and semantic mapping candidates.
- `validation/`: researcher decisions, worksheet roles, category normalization, aggregate proposals, and canonical dataset construction.
- `domain/`: stable research entities such as lexical units, raters, annotations, and validated datasets.
- `statistics/`: descriptive, pairwise, multi-rater, tendency, benchmark, grouped, and grammatical-category association analyses.
- `review/`: unit-level disagreement construction and audit views.
- `figures/`: figure datasets plus interactive and publication renderers.
- `reporting/`: comparison PDF, LaTeX helpers, and reporting text.
- `persistence/`: local research projects, immutable source copies, versions, hashes, and audit history.
- `export/`: validated datasets, structured workbooks, manifests, and research packages.
- `ui/`: Streamlit shell, navigation, filters, and page renderers.

## Design principles

1. **Automate detection, never automate trust.** Import inference can suggest a mapping, but decisions that change analytical meaning remain visible to the researcher.
2. **Preserve the source.** Original workbooks are read, copied for provenance when appropriate, and never rewritten by the analytical workflow.
3. **Model identity before statistics.** A lexical string alone is not a stable unit key; source, lexical form, grammatical category, and occurrence information are used to prevent accidental many-to-one matching.
4. **Separate statistical questions.** Agreement, marginal classification tendency, category association, and expert-benchmark performance are presented as different analyses.
5. **Keep outputs traceable.** Figures and reports can be linked to validated data, active configuration, and hashes.
6. **Local-first by default.** The application runs on the researcher's machine and does not require a remote service for core analysis.
