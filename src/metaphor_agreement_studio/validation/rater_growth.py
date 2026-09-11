from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import replace

from metaphor_agreement_studio.domain.imports import AlignmentResult, AlignmentUnit, ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation
from metaphor_agreement_studio.import_engine.alignment import align_units


class RaterMergeBlocked(RuntimeError):
    """Raised when a separate-rater file still needs explicit alignment decisions."""


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _alignment_units(dataset: ValidatedDataset) -> tuple[AlignmentUnit, ...]:
    source_names = {source.source_id: source.display_name for source in dataset.sources}
    return tuple(
        AlignmentUnit(
            unit_id=unit.unit_id,
            source_identity=source_names.get(unit.source_id, unit.source_id),
            lexical_unit=unit.lexical_unit,
            grammatical_category=unit.grammatical_category,
            occurrence_index=unit.occurrence_index,
        )
        for unit in dataset.units
    )


def align_validated_datasets(
    reference: ValidatedDataset,
    incoming: ValidatedDataset,
) -> AlignmentResult:
    """Align an already validated incoming workbook against the current canonical dataset."""

    return align_units(_alignment_units(reference), _alignment_units(incoming))


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return prefix + hashlib.sha256(payload).hexdigest()[:20]


def merge_additional_raters(
    reference: ValidatedDataset,
    incoming: ValidatedDataset,
    alignment: AlignmentResult,
    *,
    accepted_probable_incoming_ids: tuple[str, ...] = (),
) -> ValidatedDataset:
    """Merge only new raters after all uncertain unit matches have been explicitly accepted.

    The canonical unit/source layer always comes from ``reference``. Incoming workbook units are
    used only to map new-rater annotations onto those canonical unit ids.
    """

    accepted = set(accepted_probable_incoming_ids)
    unresolved_probable = [
        match for match in alignment.probable if match.incoming.unit_id not in accepted
    ]
    if unresolved_probable or alignment.no_match:
        parts: list[str] = []
        if unresolved_probable:
            parts.append(f"{len(unresolved_probable)} probable match(es) still need confirmation")
        if alignment.no_match:
            parts.append(f"{len(alignment.no_match)} unit(s) have no match")
        raise RaterMergeBlocked("Additional rater merge blocked: " + "; ".join(parts) + ".")

    reference_names = {_norm(rater.display_name) for rater in reference.raters}
    new_raters = tuple(
        rater for rater in incoming.raters if _norm(rater.display_name) not in reference_names
    )
    if not new_raters:
        raise RaterMergeBlocked("Additional rater merge blocked: no new rater was found in the incoming file.")

    new_rater_ids = {rater.rater_id for rater in new_raters}
    unit_map: dict[str, str] = {}
    for match in alignment.matches:
        if match.reference is None:
            continue
        if match.status.value == "probable" and match.incoming.unit_id not in accepted:
            continue
        unit_map[match.incoming.unit_id] = match.reference.unit_id

    new_annotations: list[Annotation] = []
    for annotation in incoming.annotations:
        if annotation.rater_id not in new_rater_ids:
            continue
        reference_unit_id = unit_map.get(annotation.unit_id)
        if reference_unit_id is None:
            continue
        new_annotations.append(
            replace(
                annotation,
                annotation_id=_stable_id(
                    "ann_", reference_unit_id, annotation.rater_id, annotation.import_id
                ),
                unit_id=reference_unit_id,
            )
        )

    expected = len(reference.units) * len(new_raters)
    if len(new_annotations) != expected:
        raise RaterMergeBlocked(
            "Additional rater merge blocked: the incoming ratings do not cover every canonical unit."
        )

    decision_ids = {item.decision_id for item in reference.validation_decisions}
    incoming_decisions = []
    for item in incoming.validation_decisions:
        if item.decision_id in decision_ids:
            item = replace(
                item,
                decision_id=_stable_id(
                    "decision_",
                    incoming.dataset_id,
                    item.decision_type,
                    item.target_id,
                    item.validated_value,
                ),
            )
        decision_ids.add(item.decision_id)
        incoming_decisions.append(item)

    dataset_id = _stable_id(
        "dataset_",
        reference.dataset_id,
        incoming.dataset_id,
        *(sorted(accepted)),
    )
    return ValidatedDataset(
        dataset_id=dataset_id,
        sources=reference.sources,
        units=reference.units,
        raters=reference.raters + new_raters,
        annotations=reference.annotations + tuple(new_annotations),
        quality_notes=reference.quality_notes + incoming.quality_notes,
        validation_decisions=reference.validation_decisions + tuple(incoming_decisions),
    )
