from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SOLVER_DIR = ROOT_DIR / "src" / "solver"

OUTPUT_TEXT_MARKERS = (
    "OFFICIAL UNIVERSITY",
    "Complete System #",
    "Schedule #",
    "=== SEMESTER:",
    "[TERM:",
    "EMPTY SCHEDULE",
    "EMPTY PERIOD",
    "Stopped after writing",
    "Auto limit wrote",
)


def test_scheduler_modules_delegate_text_formatting_to_output_layer():
    violations = []

    for path in sorted(SOLVER_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in OUTPUT_TEXT_MARKERS:
            if marker in text:
                violations.append(f"{path.relative_to(ROOT_DIR)} contains {marker!r}")

    assert violations == []
