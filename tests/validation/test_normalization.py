from metaphor_agreement_studio.validation.normalization import propose_category_normalizations


def test_adjetive_is_proposed_as_adjective_without_collapsing_distinct_categories() -> None:
    proposals = propose_category_normalizations(
        ["Adjetive", "Adverb", "Adverb (idiom)", "Phrasal verb"]
    )

    assert proposals["Adjetive"].proposed == "Adjective"
    assert proposals["Adjetive"].confidence.value == "high"
    assert "Adverb" not in proposals
    assert "Adverb (idiom)" not in proposals
    assert "Phrasal verb" not in proposals


def test_case_and_whitespace_normalization_is_proposed_without_mutating_input() -> None:
    labels = [" noun ", "VERB"]

    proposals = propose_category_normalizations(labels)

    assert proposals[" noun "].proposed == "Noun"
    assert proposals["VERB"].proposed == "Verb"
    assert labels == [" noun ", "VERB"]
