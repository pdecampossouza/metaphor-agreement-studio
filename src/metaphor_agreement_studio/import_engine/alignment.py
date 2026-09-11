from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from collections.abc import Iterable

from metaphor_agreement_studio.domain.imports import (
    AlignmentMatch,
    AlignmentResult,
    AlignmentStatus,
    AlignmentUnit,
)


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _punctuation_free(value: str) -> str:
    return "".join(ch for ch in _norm(value) if ch.isalnum() or ch.isspace())


def _exact_key(unit: AlignmentUnit) -> tuple[str, str, str, int]:
    return (
        _norm(unit.source_identity),
        _norm(unit.lexical_unit),
        _norm(unit.grammatical_category),
        unit.occurrence_index,
    )


def _probable_compatible(reference: AlignmentUnit, incoming: AlignmentUnit) -> bool:
    return (
        _norm(reference.source_identity) == _norm(incoming.source_identity)
        and _norm(reference.grammatical_category) == _norm(incoming.grammatical_category)
        and reference.occurrence_index == incoming.occurrence_index
    )


def align_units(
    reference_units: Iterable[AlignmentUnit],
    incoming_units: Iterable[AlignmentUnit],
    probable_threshold: float = 0.9,
) -> AlignmentResult:
    reference = tuple(reference_units)
    incoming = tuple(incoming_units)
    exact_index = {_exact_key(item): item for item in reference}
    used_reference_ids: set[str] = set()
    matches: list[AlignmentMatch] = []

    unresolved: list[AlignmentUnit] = []
    for item in incoming:
        found = exact_index.get(_exact_key(item))
        if found is not None and found.unit_id not in used_reference_ids:
            used_reference_ids.add(found.unit_id)
            matches.append(
                AlignmentMatch(
                    incoming=item,
                    reference=found,
                    status=AlignmentStatus.EXACT,
                    similarity=1.0,
                    accepted=True,
                    evidence="Source, lexical unit, POS, and occurrence index match exactly.",
                )
            )
        else:
            unresolved.append(item)

    for item in unresolved:
        candidates: list[tuple[float, AlignmentUnit]] = []
        incoming_text = _punctuation_free(item.lexical_unit)
        for candidate in reference:
            if candidate.unit_id in used_reference_ids or not _probable_compatible(candidate, item):
                continue
            score = SequenceMatcher(None, _punctuation_free(candidate.lexical_unit), incoming_text).ratio()
            if score >= probable_threshold:
                candidates.append((score, candidate))
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        if candidates:
            score, found = candidates[0]
            used_reference_ids.add(found.unit_id)
            matches.append(
                AlignmentMatch(
                    incoming=item,
                    reference=found,
                    status=AlignmentStatus.PROBABLE,
                    similarity=score,
                    accepted=False,
                    evidence="Normalized punctuation-insensitive text suggests a match; researcher confirmation is required.",
                )
            )
        else:
            matches.append(
                AlignmentMatch(
                    incoming=item,
                    reference=None,
                    status=AlignmentStatus.NO_MATCH,
                    similarity=0.0,
                    accepted=False,
                    evidence="No occurrence-safe exact or probable match was found.",
                )
            )

    order = {item.unit_id: index for index, item in enumerate(incoming)}
    matches.sort(key=lambda match: order[match.incoming.unit_id])
    return AlignmentResult(matches=tuple(matches))
