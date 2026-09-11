import importlib.util
from pathlib import Path


def load_app_module():
    spec = importlib.util.spec_from_file_location("mas_app", Path("app.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_path_uses_environment_override(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    monkeypatch.setenv("MAS_WORKSPACE", str(tmp_path))
    assert app.workspace_path() == tmp_path.resolve()


def test_main_is_importable_without_starting_streamlit() -> None:
    app = load_app_module()
    assert callable(app.main)
