from pathlib import Path


def test_data_validation_workspace_can_commit_separate_validated_rater_file() -> None:
    source = Path("src/metaphor_agreement_studio/ui/pages/validation.py").read_text(encoding="utf-8")
    assert "merge_additional_raters" in source
    assert "align_validated_datasets" in source
    assert "Add validated rater" in source
    assert "Probable matches are never accepted automatically" in source
    assert "accepted_probable_incoming_ids" in source
    assert "phase3_analysis_cache" in source
