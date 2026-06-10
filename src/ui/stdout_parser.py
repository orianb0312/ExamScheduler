"""Compatibility import for the stdout adapter.

The parser lives in ``src.services`` so PyQt widgets do not own output parsing.
"""

from src.services.schedule_output_service import StdoutScheduleParser

__all__ = ["StdoutScheduleParser"]
