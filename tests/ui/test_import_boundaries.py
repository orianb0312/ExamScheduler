import ast
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
UI_DIR = SRC_DIR / "ui"
SERVICES_DIR = SRC_DIR / "services"

FORBIDDEN_UI_IMPORT_PREFIXES = (
    "src.workflow",
    "src.parser",
    "src.solver",
    "src.rules",
    "src.models",
    "src.output",
    "src.validation",
    "src.interfaces",
)


def _python_files(root: Path):
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _imports_for(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    return imports


def test_ui_package_does_not_import_v1_core_modules():
    violations = []

    for path in _python_files(UI_DIR):
        for module in _imports_for(path):
            if module.startswith(FORBIDDEN_UI_IMPORT_PREFIXES):
                violations.append(f"{path.relative_to(ROOT_DIR)} imports {module}")

    assert violations == []


def test_v1_core_does_not_import_ui_or_pyqt6():
    violations = []

    for path in _python_files(SRC_DIR):
        if UI_DIR in path.parents:
            continue
        for module in _imports_for(path):
            if module.startswith("src.ui") or module.startswith("PyQt6"):
                violations.append(f"{path.relative_to(ROOT_DIR)} imports {module}")

    assert violations == []


def test_ui_uses_qprocess_without_threading_imports():
    violations = []
    forbidden_tokens = ("QThread", "threading", "ThreadPoolExecutor")

    for path in _python_files(UI_DIR):
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                violations.append(f"{path.relative_to(ROOT_DIR)} contains {token}")

    assert violations == []


def test_file_loading_service_does_not_depend_on_ui_or_pyqt6():
    violations = []

    for path in _python_files(SERVICES_DIR):
        for module in _imports_for(path):
            if module.startswith("src.ui") or module.startswith("PyQt6"):
                violations.append(f"{path.relative_to(ROOT_DIR)} imports {module}")

    assert violations == []
