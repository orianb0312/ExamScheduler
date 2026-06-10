"""Small text protocol used between the PyQt UI and the scheduler process."""

# The worker prints this after each generated page so the UI can flush the page.
BATCH_END_MARKER = "__EXAM_SCHEDULER_BATCH_END__"

# The UI sends these commands through QProcess stdin while the worker is alive.
LAZY_NEXT_COMMAND = "NEXT"
LAZY_STOP_COMMAND = "STOP"
