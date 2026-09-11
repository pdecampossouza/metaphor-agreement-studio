from __future__ import annotations

import json
from pathlib import Path

from metaphor_agreement_studio.export.manifest import ManifestContext, build_manifest


def test_manifest_contains_reproducibility_fields_and_sha256(tmp_path: Path) -> None:
    source = tmp_path / "Eduardo.xlsx"
    source.write_bytes(b"source workbook")
    context = ManifestContext(
        project_name="Metaphor Study",
        dataset_version="v1.0",
        analysis_version="A-003",
        source_files=(source,),
        raters=("Eduardo", "Braulio"),
        source_groups=("Kadouch", "Mephisto"),
        analysis_settings={"multiple_testing_correction": "holm", "analysis_perspective": "no_reference"},
        software_version="0.6.0",
        generated_at="2026-09-05T22:00:00+00:00",
    )
    manifest = build_manifest(context)
    assert manifest["project_name"] == "Metaphor Study"
    assert manifest["dataset_version"] == "v1.0"
    assert manifest["analysis_version"] == "A-003"
    assert manifest["raters"] == ["Eduardo", "Braulio"]
    assert manifest["analysis_settings"]["multiple_testing_correction"] == "holm"
    assert len(manifest["source_files"][0]["sha256"]) == 64
    json.dumps(manifest)
