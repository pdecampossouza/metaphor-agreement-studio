from pathlib import Path

from metaphor_agreement_studio.persistence.source_files import sha256_file, store_source_file


def test_store_source_file_preserves_original_import_bytes(tmp_path: Path) -> None:
    external = tmp_path / "outside" / "ratings.xlsx"
    external.parent.mkdir()
    original = b"original workbook bytes"
    external.write_bytes(original)
    project_root = tmp_path / "project"

    stored = store_source_file(external, project_root)
    external.write_bytes(b"changed outside after import")

    assert stored.stored_path.read_bytes() == original
    assert stored.sha256 == sha256_file(stored.stored_path)
    assert stored.byte_length == len(original)
    assert stored.stored_path.parent == project_root / "source_files"


def test_identical_file_is_deduplicated_by_hash(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    first = tmp_path / "a" / "ratings.xlsx"
    second = tmp_path / "b" / "other-name.xlsx"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"same")
    second.write_bytes(b"same")

    one = store_source_file(first, project_root)
    two = store_source_file(second, project_root)

    assert one.file_id == two.file_id
    assert one.stored_path == two.stored_path
    assert len(list((project_root / "source_files").iterdir())) == 1


def test_name_collision_with_different_bytes_does_not_overwrite(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    first = tmp_path / "a" / "ratings.xlsx"
    second = tmp_path / "b" / "ratings.xlsx"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    one = store_source_file(first, project_root)
    two = store_source_file(second, project_root)

    assert one.stored_path != two.stored_path
    assert one.stored_path.read_bytes() == b"one"
    assert two.stored_path.read_bytes() == b"two"
    assert two.sha256[:8] in two.stored_path.stem


def test_store_source_file_closes_temp_descriptor_before_reusing_path(tmp_path: Path, monkeypatch) -> None:
    import os
    import tempfile as std_tempfile

    from metaphor_agreement_studio.persistence import source_files as module

    source = tmp_path / "outside" / "ratings.xlsx"
    source.parent.mkdir()
    source.write_bytes(b"windows-safe")
    project_root = tmp_path / "project"
    descriptor: dict[str, int] = {}
    real_mkstemp = std_tempfile.mkstemp
    real_unlink = Path.unlink

    def tracked_mkstemp(*args, **kwargs):
        fd, name = real_mkstemp(*args, **kwargs)
        descriptor["fd"] = fd
        return fd, name

    def assert_closed_then_unlink(path: Path, *args, **kwargs):
        fd = descriptor.get("fd")
        if fd is not None:
            try:
                os.fstat(fd)
            except OSError:
                pass
            else:
                raise AssertionError("temporary descriptor must be closed before path reuse")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(module.tempfile, "mkstemp", tracked_mkstemp)
    monkeypatch.setattr(Path, "unlink", assert_closed_then_unlink)

    stored = module.store_source_file(source, project_root)
    assert stored.stored_path.read_bytes() == b"windows-safe"
