from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable

from metaphor_agreement_studio.domain.imports import (
    CellSnapshot,
    RaterColumnCandidate,
    TableCandidate,
    TableRowCandidate,
    WorkbookInspection,
)

_ORDER_HEADERS = {"nr", "no", "number", "n"}
_LEXICAL_HEADERS = {"unidade lexical", "lexical unit"}
_POS_HEADERS = {"categoria gramatical", "grammatical category"}
_RATER_GROUP_HEADERS = {"avaliadores", "raters", "rater", "evaluators", "evaluator"}


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip().casefold()
    text = text.rstrip(" :?.")
    return text


def _is_annotation_header(value: object) -> bool:
    text = _normalize(value)
    return "metafora" in text or "metaphor" in text


def _cell_map(cells: Iterable[CellSnapshot]) -> dict[tuple[int, int], CellSnapshot]:
    return {(cell.row, cell.column): cell for cell in cells}


def _find_rater_name(
    cells: dict[tuple[int, int], CellSnapshot],
    header_row: int,
    column: int,
) -> tuple[str, str]:
    for row in range(header_row - 1, max(0, header_row - 4), -1):
        cell = cells.get((row, column))
        if cell is None or cell.raw_value is None:
            continue
        value = str(cell.raw_value).strip()
        if value and _normalize(value) not in {"avaliadores", "raters", "rater", "evaluators"}:
            return value, cell.coordinate
    return f"Rater {column}", cells[(header_row, column)].coordinate


def _source_title(
    cells: dict[tuple[int, int], CellSnapshot],
    header_row: int,
    order_column: int,
    sheet_name: str,
) -> tuple[str, str | None]:
    for row in range(header_row - 1, max(0, header_row - 7), -1):
        cell = cells.get((row, order_column))
        if cell and cell.raw_value is not None:
            value = str(cell.raw_value).strip()
            if value:
                return value, cell.coordinate
    return f"{sheet_name} · table at row {header_row}", None


def _as_order(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _table_id(sheet_name: str, header_row: int, source_title: str) -> str:
    payload = f"{sheet_name}|{header_row}|{source_title}".encode("utf-8")
    return "tbl_" + hashlib.sha256(payload).hexdigest()[:16]


def detect_tables(inspection: WorkbookInspection) -> tuple[TableCandidate, ...]:
    detected: list[TableCandidate] = []
    for sheet in inspection.sheets:
        cells = _cell_map(sheet.cells)
        for row in range(1, sheet.max_row + 1):
            row_cells = [cells[(row, col)] for col in range(1, sheet.max_column + 1)]
            normalized = {_normalize(cell.raw_value): cell.column for cell in row_cells if cell.raw_value is not None}
            order_columns = [col for text, col in normalized.items() if text in _ORDER_HEADERS]
            lexical_columns = [col for text, col in normalized.items() if text in _LEXICAL_HEADERS]
            pos_columns = [col for text, col in normalized.items() if text in _POS_HEADERS]
            if not order_columns or not lexical_columns or not pos_columns:
                continue
            order_col = min(order_columns)
            lexical_col = min(col for col in lexical_columns if col > order_col) if any(col > order_col for col in lexical_columns) else min(lexical_columns)
            pos_col = min(col for col in pos_columns if col > lexical_col) if any(col > lexical_col for col in pos_columns) else min(pos_columns)
            if not (order_col < lexical_col < pos_col):
                continue

            rater_cols: list[RaterColumnCandidate] = []
            col = pos_col + 1
            while col <= sheet.max_column:
                header_cell = cells[(row, col)]
                if not _is_annotation_header(header_cell.raw_value):
                    if rater_cols:
                        break
                    col += 1
                    continue
                display_name, name_cell = _find_rater_name(cells, row, col)
                rater_cols.append(
                    RaterColumnCandidate(
                        display_name=display_name,
                        column=col,
                        name_cell=name_cell,
                        header_cell=header_cell.coordinate,
                        question_header=str(header_cell.raw_value or ""),
                    )
                )
                col += 1

            # Some research workbooks use the rater names themselves as the
            # annotation-column headers and place a grouped "Avaliadores" /
            # "Raters" label immediately above them.  In those sheets the
            # annotation cells may be intentionally blank and encoded only by
            # fill colour, so requiring a "Metaphor?" header would hide the
            # entire table before the existing colour-mapping workflow can run.
            if not rater_cols:
                group_cell = cells.get((row - 1, pos_col + 1))
                if group_cell is not None and _normalize(group_cell.raw_value) in _RATER_GROUP_HEADERS:
                    col = pos_col + 1
                    while col <= sheet.max_column:
                        header_cell = cells[(row, col)]
                        if header_cell.raw_value is None:
                            break
                        display_name = str(header_cell.raw_value).strip()
                        if not display_name:
                            break
                        rater_cols.append(
                            RaterColumnCandidate(
                                display_name=display_name,
                                column=col,
                                name_cell=header_cell.coordinate,
                                header_cell=header_cell.coordinate,
                                question_header=str(group_cell.raw_value or "Raters"),
                            )
                        )
                        col += 1
            if not rater_cols:
                continue

            title, title_cell = _source_title(cells, row, order_col, sheet.name)
            data_rows: list[TableRowCandidate] = []
            data_row = row + 1
            while data_row <= sheet.max_row:
                order_value = _as_order(cells[(data_row, order_col)].raw_value)
                lexical_raw = cells[(data_row, lexical_col)].raw_value
                pos_raw = cells[(data_row, pos_col)].raw_value
                if order_value is None or lexical_raw is None or pos_raw is None:
                    break
                lexical = str(lexical_raw)
                pos = str(pos_raw)
                annotations = tuple(cells[(data_row, rater.column)] for rater in rater_cols)
                data_rows.append(
                    TableRowCandidate(
                        row=data_row,
                        order=order_value,
                        lexical_unit=lexical,
                        grammatical_category=pos,
                        annotation_cells=annotations,
                    )
                )
                data_row += 1
            if not data_rows:
                continue

            detected.append(
                TableCandidate(
                    table_id=_table_id(sheet.name, row, title),
                    workbook_path=inspection.path,
                    sheet_name=sheet.name,
                    source_title=title,
                    title_cell=title_cell,
                    header_row=row,
                    data_start_row=data_rows[0].row,
                    data_end_row=data_rows[-1].row,
                    first_column=order_col,
                    last_column=rater_cols[-1].column,
                    order_column=order_col,
                    lexical_unit_column=lexical_col,
                    grammatical_category_column=pos_col,
                    rater_columns=tuple(rater_cols),
                    rows=tuple(data_rows),
                )
            )
    return tuple(sorted(detected, key=lambda item: (item.sheet_name, item.header_row, item.first_column)))
