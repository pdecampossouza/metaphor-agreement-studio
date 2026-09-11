# Statistical methods implemented by Metaphor Agreement Studio

This document summarizes the questions answered by the current statistical layer. It is documentation for the software, not a substitute for a study-specific statistical analysis plan.

## Rating model

For each lexical unit and rater, the validated classification is nominal and binary: metaphor, non-metaphor, or missing/unavailable. Missing values remain explicit and are not recoded as negative classifications.

## Pairwise agreement

For each rater pair, the Studio reports pairwise observed agreement and Cohen's Kappa on units observed by both raters. Pairwise confidence intervals can be estimated by lexical-unit bootstrap using the configured random seed and number of bootstrap samples. Positive/metaphor-specific and negative/non-metaphor-specific agreement are also available when their denominators are defined.

## Multi-rater agreement

When three or more raters are selected, Fleiss' Kappa is the primary global chance-corrected agreement coefficient. In the implemented doctoral protocol it is also recomputed within grammatical categories and source tables. The current Fleiss calculation uses units complete across all selected raters.

Krippendorff's nominal alpha is reported as a complementary multi-rater measure and can use units with at least two observed ratings. The public release uses the Studio's internal nominal coincidence-matrix implementation, avoiding a runtime dependency on an external alpha package.

## Classification tendency

Cochran's Q is reported separately from agreement coefficients. It tests whether selected raters have the same marginal tendency to classify units as metaphorical. It is not an agreement coefficient. Pairwise McNemar tests provide post-hoc comparisons of marginal classification tendency.

Multiple pairwise p-values can be left unadjusted or corrected with Holm or Benjamini-Hochberg, depending on the active analysis configuration.

## Grammatical-category association

The Studio can test, separately within each selected rater, whether metaphor/non-metaphor classification is associated with grammatical category using the Fisher-Freeman-Halton exact test for an R x 2 contingency table.

The researcher chooses one of two category-inclusion rules:

1. **Exclude categories with fewer than five occurrences** in the selected analytical scope; or
2. **Include all grammatical categories**.

The five-occurrence threshold is a researcher-selected analysis rule, not a mathematical requirement of the exact test. The selected rule is recorded in the analysis configuration and comparison PDF.

Because the test is evaluated for multiple raters, the reported per-rater p-values can also receive the configured multiple-testing correction (Holm is the recommended confirmatory default in the current workflow).

A significant Fisher-Freeman-Halton result indicates evidence of association between grammatical category and classification within that rater. It does not, by itself, establish inter-rater agreement and does not identify which individual category is responsible for a global association.

## Reference and expert perspectives

A **Reference rater** changes presentation and prioritization but does not change the symmetry of Cohen/Fleiss agreement calculations. An **Expert benchmark** is an explicitly directional choice and enables sensitivity, specificity, precision, recall, and confusion counts relative to the selected benchmark.

## Missingness and estimability

The software uses estimator-specific missing-data rules rather than deleting every unit that contains any missing value. Results carry effective sample sizes and explicit statuses for descriptive-only or non-estimable cases. A non-estimable Kappa caused by no class variation is distinguished from a software error.

## Reproducibility

Analysis outputs can record dataset-content SHA-256, analysis-configuration SHA-256, selected raters/sources/categories, perspective, reference/benchmark choice, random seed, bootstrap sample count, category-inclusion rule, and multiple-testing correction.
