import sqlite3
from pathlib import Path

import pytest

from metaphor_agreement_studio.persistence.db import initialize_database, open_database, transaction


REQUIRED_TABLES = {
    "project",
    "source_files",
    "imports",
    "sources",
    "raters",
    "lexical_units",
    "raw_annotations",
    "validated_annotations",
    "validation_decisions",
    "dataset_versions",
    "analysis_versions",
    "audit_events",
    "artifacts",
}


def test_initialize_database_creates_required_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "project.db"
    initialize_database(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert REQUIRED_TABLES <= tables
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_open_database_enables_foreign_keys_and_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "project.db"
    initialize_database(db_path)
    with open_database(db_path) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        row = conn.execute("SELECT 1 AS value").fetchone()
        assert row["value"] == 1


def test_transaction_rolls_back_on_exception(tmp_path: Path) -> None:
    db_path = tmp_path / "project.db"
    initialize_database(db_path)
    with open_database(db_path) as conn:
        with pytest.raises(RuntimeError):
            with transaction(conn):
                conn.execute(
                    "INSERT INTO project VALUES (?, ?, ?, ?, ?)",
                    ("p1", "Name", "now", "now", "0.5.0"),
                )
                raise RuntimeError("boom")
        assert conn.execute("SELECT COUNT(*) FROM project").fetchone()[0] == 0
