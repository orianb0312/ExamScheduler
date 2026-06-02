"""Standalone PyQt6 UI package for ExamScheduler v2.0."""


def main() -> int:
    """Run the desktop UI entry point."""
    from src.ui.app import run

    return run()


__all__ = ["main"]
