# ExamScheduler

ExamScheduler is a Python desktop and command-line application for generating
valid university exam schedules from course, exam-period, and selected-program
files.

The project combines a tested scheduling engine with a PyQt6 desktop interface.
Users can load course/date data, select study programs, edit exam-period
calendar days, generate schedules, page through large result sets, and save the
currently selected schedule to a readable file.

## Main Features

- PyQt6 desktop UI for file loading, program selection, calendar editing, and schedule review.
- Exact period-level schedule generation.
- Complete-system counting across multiple exam periods.
- Lazy schedule streaming in pages of 1,000 generated complete systems.
- `QProcess` execution boundary so long scheduling runs do not freeze the UI.
- Readable export for the currently displayed/selected schedule.
- Architecture tests that guard UI/backend boundaries and local-only execution.

## Quick Start

Run all commands from the project root.

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Launch the desktop app

```powershell
python gui_main.py
```

If you prefer to call the CLI directly, use `main.py` as shown below.

## Desktop Workflow

The V2 desktop app guides the user through one complete workflow:

1. Load or update course and exam-date files.
2. Select up to five study programs.
3. Review and edit exam-period calendar days.
4. Generate schedules through the existing backend.
5. Page through generated complete systems.
6. Save the currently displayed schedule to a readable file.

Long-running scheduling work is launched through `QProcess`, not directly from
widgets. This keeps the PyQt event loop responsive while `main.py` parses,
filters, schedules, and streams output.

## CLI Usage

Count all complete systems without writing them:

```powershell
python main.py --mode complete-count
```

Generate period-level schedules:

```powershell
python main.py --mode period
```

Write a bounded number of complete systems:

```powershell
python main.py --mode complete-write --max-systems 1000
```

Write as many complete systems as fit within a time limit:

```powershell
python main.py --mode auto --time-limit 30
```

Stream complete systems for desktop/UI callers:

```powershell
python main.py --mode auto --stream-schedules
```

Generate the first page, then wait for `NEXT` / `STOP` commands on stdin:

```powershell
python main.py --mode auto --lazy-schedules
```

Show all CLI options:

```powershell
python main.py --help
```

## Default Input and Output Files

Default input files are configured in `config.json`:

```text
data/V1.0CourseDB.txt
data/V1.0 ExamDates.txt
data/Programs.txt
```

Default output settings:

```text
base directory: outputs
master filename: university_master_schedule
```

You can override input files from the CLI:

```powershell
python main.py --mode auto --course-file path\to\courses.txt --dates-file path\to\dates.txt --user-file path\to\programs.txt
```

## Scheduling Rule

The active rule is `AcademicConflictRule`.

Two exams cannot be scheduled on the same date if they belong to the same
program and study year and at least one of the two courses is obligatory. If
both courses are electives for that same cohort, the conflict is allowed.

## Algorithm Summary

The period scheduler:

1. Builds the valid date set for the exam period.
2. Filters relevant exam courses.
3. Builds a conflict graph between courses.
4. Splits the graph into connected components.
5. Solves each component with backtracking and MRV ordering.
6. Combines independent component schedules.

The complete-system scheduler:

1. Builds period-level schedule sets.
2. Counts complete systems as the product of period schedule counts.
3. Streams complete systems instead of materializing huge outputs at once.
4. Uses a default complete-system page size of 1,000 for lazy UI paging.

## Lazy Streaming Protocol

The desktop UI and CLI share a small local text protocol:

```text
NEXT
STOP
__EXAM_SCHEDULER_BATCH_END__
```

- `NEXT` asks the running scheduler process for another page.
- `STOP` cancels or closes the lazy stream.
- `__EXAM_SCHEDULER_BATCH_END__` marks the end of the current generated page.

This protocol is intentionally local and simple. There is no HTTP server, no
socket dependency, and no hidden client-server architecture.

## Architecture

Dependency direction:

```text
PyQt6 UI -> services/adapters -> V1 application/domain
```

Main layers:

```text
gui_main.py
src/ui/                  PyQt widgets, navigation, signals, styles
src/services/            UI-facing services and adapters
src/process_protocol.py  NEXT / STOP / batch-end markers
main.py                  CLI entry point and workflow dispatcher
src/workflow.py          parsing, filtering, scheduling workflow
src/parser/              file parsing and factories
src/models/              domain models
src/rules/               scheduling rules
src/solver/              period and complete-system schedulers
src/output/              output models, formatting, text writing
src/validation/          independent validation helpers
```

The UI does not import solver classes directly. Long-running work crosses the
boundary through `src/ui/process_runner.py`, which wraps `QProcess` and converts
stdout, stderr, finish events, and errors into UI signals.

## Tests

Install dependencies first, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The test suite covers:

- parser validation
- model behavior
- academic conflict rules
- period scheduler correctness
- complete-system counting and streaming
- workflow integration
- selected schedule file writing
- PyQt UI behavior
- QProcess/local execution boundaries
- network isolation
- import-direction architecture guards

Use the pytest summary as the source of truth for the current test count.

## Documentation and Presentation Files

Project documentation is in `docs/`:

- `docs/project_overview.md`
- `docs/diagrams.md`
- `docs/layer_boundaries.md`
- `docs/qprocess_boundaries.md`
- `docs/testing_and_validation.md`
- `docs/test_specification.md`
- `docs/ExamScheduler_Test_Specification_v1_0.docx`
- `docs/ExamScheduler_v2_Progress_Presentation.pptx`
- `docs/ExamScheduler_V2_Presentation_Restyled.pptx`

## Notes for Future Work

The current architecture keeps the proven scheduler behind a local process
boundary. The most natural future improvement is replacing human-readable stdout
parsing with structured JSON events while preserving the same UI/service/backend
separation.
