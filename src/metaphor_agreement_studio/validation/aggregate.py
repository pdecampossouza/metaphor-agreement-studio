from __future__ import annotations

import itertools
import re
import unicodedata

from metaphor_agreement_studio.domain.imports import AggregateCandidate, TableCandidate


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def _signatures(table: TableCandidate) -> tuple[tuple[str, str], ...]:
    return tuple((_norm(row.lexical_unit), _norm(row.grammatical_category)) for row in table.rows)


def detect_aggregate_sources(tables: tuple[TableCandidate, ...]) -> tuple[AggregateCandidate, ...]:
    proposals: list[AggregateCandidate] = []
    for aggregate in tables:
        possible = [
            table
            for table in tables
            if table.table_id != aggregate.table_id
            and table.sheet_name == aggregate.sheet_name
            and table.row_count < aggregate.row_count
        ]
        possible.sort(key=lambda table: table.header_row)
        target = _signatures(aggregate)
        matched_components: tuple[TableCandidate, ...] | None = None
        for count in range(2, len(possible) + 1):
            for combo in itertools.combinations(possible, count):
                if sum(table.row_count for table in combo) != aggregate.row_count:
                    continue
                sequence = tuple(signature for table in combo for signature in _signatures(table))
                if sequence == target:
                    matched_components = combo
                    break
            if matched_components is not None:
                break
        if matched_components is None:
            continue
        proposals.append(
            AggregateCandidate(
                aggregate_table_id=aggregate.table_id,
                aggregate_source_title=aggregate.source_title,
                component_table_ids=tuple(table.table_id for table in matched_components),
                matched_units=len(target),
                coverage=1.0 if target else 0.0,
            )
        )
    return tuple(proposals)
