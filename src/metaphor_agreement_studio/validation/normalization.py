from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from metaphor_agreement_studio.domain.imports import ConfidenceLevel, NormalizationProposal

_CANONICAL = {
    "noun": "Noun",
    "verb": "Verb",
    "adjective": "Adjective",
    "adverb": "Adverb",
    "pronoun": "Pronoun",
    "preposition": "Preposition",
    "phrasal verb": "Phrasal verb",
    "adverb (idiom)": "Adverb (idiom)",
}
_KNOWN_TYPOS = {"adjetive": "Adjective"}


def _key(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", text).strip().casefold()


def propose_category_normalizations(
    labels: Iterable[str],
) -> dict[str, NormalizationProposal]:
    proposals: dict[str, NormalizationProposal] = {}
    for original in labels:
        key = _key(original)
        if key in _KNOWN_TYPOS:
            proposals[original] = NormalizationProposal(
                original=original,
                proposed=_KNOWN_TYPOS[key],
                reason="Known spelling normalization",
                confidence=ConfidenceLevel.HIGH,
            )
            continue
        canonical = _CANONICAL.get(key)
        if canonical is not None and original != canonical:
            proposals[original] = NormalizationProposal(
                original=original,
                proposed=canonical,
                reason="Case and whitespace normalization",
                confidence=ConfidenceLevel.HIGH,
            )
    return proposals
