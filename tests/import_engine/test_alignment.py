from metaphor_agreement_studio.domain.imports import AlignmentUnit
from metaphor_agreement_studio.import_engine.alignment import align_units


def unit(source: str, text: str, pos: str, occurrence: int, unit_id: str) -> AlignmentUnit:
    return AlignmentUnit(
        unit_id=unit_id,
        source_identity=source,
        lexical_unit=text,
        grammatical_category=pos,
        occurrence_index=occurrence,
    )


def test_repeated_tokens_align_by_occurrence_index() -> None:
    reference = (
        unit("Mephisto", "hand", "Noun", 1, "ref-1"),
        unit("Mephisto", "hand", "Noun", 2, "ref-2"),
    )
    incoming = (
        unit("Mephisto", "hand", "Noun", 1, "in-1"),
        unit("Mephisto", "hand", "Noun", 2, "in-2"),
        unit("Mephisto", "hand", "Noun", 3, "in-3"),
    )

    result = align_units(reference, incoming)

    assert [(match.incoming.unit_id, match.reference.unit_id) for match in result.exact] == [
        ("in-1", "ref-1"),
        ("in-2", "ref-2"),
    ]
    assert [match.incoming.unit_id for match in result.no_match] == ["in-3"]


def test_punctuation_only_difference_is_probable_but_never_autoaccepted() -> None:
    reference = (unit("Kadouch", "positions:", "Noun", 1, "ref"),)
    incoming = (unit("Kadouch", "positions", "Noun", 1, "incoming"),)

    result = align_units(reference, incoming)

    assert len(result.probable) == 1
    match = result.probable[0]
    assert match.reference.unit_id == "ref"
    assert match.incoming.unit_id == "incoming"
    assert match.similarity >= 0.95
    assert match.accepted is False
    assert not result.exact
