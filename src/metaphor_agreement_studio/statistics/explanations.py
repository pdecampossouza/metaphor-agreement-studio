from __future__ import annotations

_EXPLANATIONS: dict[str, str] = {
    "perfect_agreement_no_variation": (
        "Observed agreement is perfect, but all ratings fall in the same class, so a "
        "chance-corrected coefficient cannot be estimated from this subset."
    ),
    "kappa_no_chance_variation": (
        "Cohen's Kappa is not estimable because the expected-agreement denominator has no variation."
    ),
    "one_item_descriptive_only": (
        "This subset contains only one lexical unit. Agreement is shown descriptively, but "
        "chance-corrected or inferential statistics are not meaningful."
    ),
    "no_complete_pairwise_observations": (
        "The selected raters have no lexical units with complete paired ratings."
    ),
    "no_complete_multirater_observations": (
        "No lexical units have complete ratings from every selected rater."
    ),
    "cochran_q_requires_two_raters": "Cochran's Q requires at least two raters.",
    "cochran_q_no_discordant_information": (
        "Cochran's Q is not estimable because the selected ratings contain no discordant information."
    ),
    "two_rater_q_related_to_mcnemar": (
        "With two raters, Cochran's Q is closely related to McNemar's test for paired binary responses."
    ),
    "mcnemar_no_discordant_pairs": (
        "McNemar's test is not informative because the two raters have no discordant pairs."
    ),
    "fleiss_complete_cases_only": (
        "Fleiss' Kappa uses only lexical units rated by every selected rater; its effective N may "
        "therefore be smaller than the dataset size."
    ),
    "krippendorff_requires_two_ratings_per_unit": (
        "Krippendorff's Alpha requires at least two available ratings on a lexical unit."
    ),
    "krippendorff_missing_tolerant": (
        "Krippendorff's Alpha was estimated using available nominal ratings and can accommodate "
        "missing ratings."
    ),
    "krippendorff_internal_nominal_fallback": (
        "The nominal Krippendorff Alpha calculation used the application's mathematically equivalent "
        "internal implementation because the optional krippendorff package was unavailable."
    ),
    "alpha_no_expected_disagreement": (
        "Krippendorff's Alpha is not estimable because there is no expected disagreement to correct for."
    ),
    "class_absent_specific_agreement": (
        "This class does not occur in the paired ratings, so class-specific agreement is not estimable."
    ),
    "class_imbalance_kappa_prevalence": (
        "The ratings are strongly imbalanced toward one class. Cohen's Kappa can be sensitive to "
        "prevalence in this situation; interpret it alongside raw agreement and class-specific agreement."
    ),
    "missing_annotations_present": (
        "Some ratings are missing. Pairwise statistics use each pair's available overlap, while "
        "multi-rater statistics report their own effective sample size."
    ),
    "benchmark_no_positive_cases": (
        "The expert benchmark contains no metaphor cases in this subset, so sensitivity and recall cannot be estimated."
    ),
    "benchmark_no_negative_cases": (
        "The expert benchmark contains no non-metaphor cases in this subset, so specificity cannot be estimated."
    ),
    "compared_rater_no_positive_predictions": (
        "The compared rater did not classify any paired units as metaphor, so precision cannot be estimated."
    ),
}


def explanation_text(key: str) -> str:
    return _EXPLANATIONS.get(key, key.replace("_", " ").capitalize() + ".")


def explanation_texts(keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(explanation_text(key) for key in keys)
