from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_ui_package_contains_diagram_entry_files():
    ui_dir = ROOT_DIR / "src" / "ui"

    expected_files = {
        "__init__.py",
        "main_window.py",
        "calendar_view.py",
        "pagination_bar.py",
        "ui_cache.py",
        "styles.qss",
    }

    assert expected_files <= {path.name for path in ui_dir.iterdir()}


def test_gui_main_is_root_desktop_entry_point():
    gui_main = ROOT_DIR / "gui_main.py"

    assert gui_main.exists()
    assert "from src.ui import main" in gui_main.read_text(encoding="utf-8")
