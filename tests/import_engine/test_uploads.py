import hashlib
from pathlib import Path

import pytest

from metaphor_agreement_studio.import_engine.uploads import (
    UnsupportedWorkbookError,
    materialize_upload,
)
from metaphor_agreement_studio.state.session import (
    ADDITIONAL_WORKBOOKS_KEY,
    PRIMARY_WORKBOOK_KEY,
    add_additional_workbook,
    ensure_session_state,
    set_primary_workbook,
)


@pytest.mark.parametrize("name", ["ratings.xlsx", "ratings.XLSX", "study.xlsm"])
def test_supported_workbook_types_are_materialized_under_session_root(
    tmp_path: Path, name: str
) -> None:
    upload = materialize_upload(name, b"excel-bytes", tmp_path)

    assert upload.local_path.resolve().is_relative_to(tmp_path.resolve())
    assert upload.original_display_name == name
    assert upload.byte_length == len(b"excel-bytes")


@pytest.mark.parametrize(
    "name",
    ["ratings.csv", "ratings.xls", "archive.zip", "../../evil.xlsx", r"..\\evil.xlsx", "~$temp.xlsx"],
)
def test_unsafe_or_unsupported_workbook_names_are_rejected(tmp_path: Path, name: str) -> None:
    with pytest.raises(UnsupportedWorkbookError):
        materialize_upload(name, b"data", tmp_path)


def test_upload_bytes_and_hash_are_preserved_and_collisions_do_not_overwrite(tmp_path: Path) -> None:
    first_bytes = b"first workbook"
    second_bytes = b"second workbook"

    first = materialize_upload("ratings.xlsx", first_bytes, tmp_path)
    second = materialize_upload("ratings.xlsx", second_bytes, tmp_path)

    assert first.local_path.read_bytes() == first_bytes
    assert second.local_path.read_bytes() == second_bytes
    assert first.sha256 == hashlib.sha256(first_bytes).hexdigest()
    assert second.sha256 == hashlib.sha256(second_bytes).hexdigest()
    assert first.local_path != second.local_path


def test_session_tracks_primary_and_additional_workbooks_without_merging(tmp_path: Path) -> None:
    state = {}
    ensure_session_state(state)
    primary = materialize_upload("primary.xlsx", b"a", tmp_path / "uploads")
    additional = materialize_upload("sofia.xlsx", b"b", tmp_path / "uploads")

    set_primary_workbook(primary, state)
    add_additional_workbook(additional, state)

    assert state[PRIMARY_WORKBOOK_KEY] == primary
    assert state[ADDITIONAL_WORKBOOKS_KEY] == [additional]
