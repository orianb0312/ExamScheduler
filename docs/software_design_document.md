# ExamScheduler Software Design Document

## Purpose And Scope

This Software Design Document (SDD) records the Stage 3 design of the
ExamScheduler desktop and command-line application. It satisfies the formal
design requirement for:

- UI/UX design logic, menus, and usage examples.
- Object-oriented class architecture and Stage 3 OOP alignment.
- Readability guidance that connects implementation comments to the documented
  design.

The implementation remains a standalone offline Python application. The desktop
UI is built with PyQt6, and long-running scheduling work executes locally
through `QProcess` by launching `main.py`.

## Chapter 1: UI/UX And Menus

### Interface Design Logic

The desktop interface is designed as an operational scheduling tool rather than
a marketing-style website. The main design goals are:

- Keep the workflow linear enough for office users: load data, choose programs,
  adjust calendars and rules, generate schedules, review results.
- Keep the application responsive during expensive search operations by moving
  the solver into a local child process.
- Keep generated schedules inspectable by showing them as calendar periods
  instead of raw text only.
- Keep advanced Stage 3 features discoverable through clear tabs: dashboard
  analytics, constraint settings, sorting options, and calendar export.
- Keep V1 file compatibility by adapting UI state back into runtime text files
  before scheduling starts.

The main screen is implemented by `InputPanel` inside `MainWindow`.
`MainWindow` acts as the application controller: it owns data loading, process
execution, output parsing, calendar export, and screen changes. Individual
widgets emit signals and avoid direct scheduler calls.

### Top Navigation Menu

The top navigation menu is a horizontal tab row owned by
`src/ui/input_panel.py`.

| Menu item | Runtime state | Purpose |
| --- | --- | --- |
| Dashboard | Enabled | Shows analytics for the best generated schedule and the current generated batch. |
| Programs | Enabled | Main configuration page for file loading, study program selection, and AI copilot input. |
| Courses | Reserved/disabled | Placeholder for a future top-level course browser. Current course details open from the selected-programs table. |
| Calendar | Enabled, with no-data state before load | Shows exam periods, excluded days, and editable period dates. |
| Settings | Enabled | Shows the five Stage 3 threshold constraints with toggles and k values. |
| Schedules | Enabled after schedules exist | Shows generated complete systems, paging, sorting, saving, and calendar sync actions. |

The menu is intentionally kept inside the input shell so navigation does not
jump between unrelated windows. The only full-screen state change outside this
shell is the loading screen displayed while the scheduler process is running.

### Screen Responsibilities

**Programs screen**

The Programs screen combines the primary setup controls:

- `FileLoaderWidget` selects course and exam-date files.
- `ProgramSelectionWidget` limits selected study programs to the configured
  maximum.
- `SelectedProgramsPanel` displays chosen programs and opens
  `ProgramCoursesDialog` for course detail inspection.
- `AICopilotWidget` accepts natural-language local rule requests and sends only
  confirmed, validated rules to the backend. It implements a fail-closed
  mechanism to ensure UI stability even if local inference fails or times out.
- The `Generate Schedules` button builds a `CliRunConfig` and starts local
  scheduling.

**Calendar screen**

`CalendarView` and `CalendarPeriodList` show each exam period as calendar
cells. Users can exclude or restore days and can edit period start/end dates.
Edits are stored in `SchedulerInputState`, then written to the runtime
exam-date file before scheduling.

**Settings screen**

`ConstraintSettingsWidget` exposes the five Stage 3 hard constraints:

| Requirement | UI control | Backend parameter |
| --- | --- | --- |
| 2.1 | Toggle plus k input | `min_days_between_mandatory` |
| 2.2 | Toggle plus k input | `min_days_between_any` |
| 2.3 | Toggle plus k input | `max_elective_conflicts` |
| 2.4 | Toggle plus k input | `min_days_before_last_mandatory` |
| 2.5 | Toggle plus k input | `max_exams_per_day` |

Validation is centralized in `ConstraintSettingsPolicy`, so UI validation and
AI-generated rule validation use the same integer rules.

**Loading screen**

`LoadingView` displays progress text and a cancel action while `ProcessRunner`
owns the local `QProcess`. The UI remains responsive because the solver runs in
the child process. Cancel sends a stop request or terminates the active process.

**Schedules screen**

`OutputView` shows possible exam schedules one at a time. The main controls are:

- Previous/Next/page buttons in `PaginationBar`.
- `Save Current Schedule` for exporting the selected schedule as readable text
  or analytics.
- `Sync Current to Calendar` to generate an ICS publish/cancel file.
- `Cancel All Synced Exams` to generate ICS cancellation data for previously
  exported entries.
- `click for sort options` to open `SortingPriorityWidget`.

`ScheduleCache` stores pages as the lazy stream arrives. `ScheduleBestTracker`
tracks the best schedule according to the active Part 3 sorting priority.

### Dialogs And Secondary Menus

| Dialog or panel | Trigger | Purpose |
| --- | --- | --- |
| File chooser | Browse buttons or save/export actions | Select input files and output paths. |
| Program courses dialog | Click a selected program row | Inspect course IDs, names, semester/year, and requirement filters. |
| AI rule confirmation dialog | AI copilot proposes a rule | Compare current rules with the proposed change before applying. |
| Sorting priority panel | Sort options button | Toggle and reorder Part 3 sort metrics. |
| Calendar sync save dialog | Calendar export action | Save generated ICS content for the OS calendar application. |

The dialogs are used only where the user must confirm a file path, a rule
change, or a detailed inspection action. Routine navigation stays in the main
window.

### Usage Examples

**Example 1: Generate a schedule from default data**

1. Open the desktop application with `python gui_main.py`.
2. On Programs, keep the default course and exam-date files or choose new files.
3. Select up to five study programs.
4. Press `Generate Schedules`.
5. Review schedules on the Schedules screen and use Next/Previous to page.

**Example 2: Exclude a holiday before generation**

1. Load the input files.
2. Open Calendar from the top menu.
3. Click the holiday date or edit the period date range.
4. Return to Programs or Settings.
5. Generate schedules. The updated dates are written to the UI runtime
   exam-date file and parsed through the existing backend.

**Example 3: Apply Stage 3 constraints**

1. Open Settings.
2. Enable the desired requirement rows.
3. Enter k values according to each row's validation rule.
4. Generate schedules. `SchedulerRunConfigBuilder` writes the constraints file,
   and the backend constructs rule objects from it.

**Example 4: Sort and export a preferred schedule**

1. Generate schedules in auto or complete-write mode.
2. Open the sort options panel on the Schedules screen.
3. Enable and reorder the Part 3 criteria.
4. Inspect the best schedule and the Dashboard analytics.
5. Save the current schedule or sync it to a calendar file.

## Chapter 2: Class Architecture And OOP Design

This architecture is visually represented in the attached Class Diagram and
Sequence Diagram appended to this submission.

### Layered Architecture

The dependency direction is:

```text
PyQt6 UI -> services/adapters -> V1 application/domain
```

The reverse direction is intentionally blocked. The scheduler, parser, rules,
models, output, and validation layers do not import PyQt6 or `src.ui`.

| Layer | Main modules | Responsibility |
| --- | --- | --- |
| UI | `gui_main.py`, `src/ui/` | Widgets, screen navigation, signals, styles, user feedback. |
| Services/adapters | `src/services/` | Translate UI state into validated files, CLI commands, analytics, calendar export, and output adapters. |
| Process protocol | `src/process_protocol.py` | Local text commands for lazy schedule paging: `NEXT`, `STOP`, and batch-end marker. |
| Workflow | `main.py`, `src/workflow.py` | CLI dispatch, parser orchestration, rule construction, scheduler calls. |
| Domain model | `src/models/` | Course, affiliation, evaluation strategy, exam period, date exclusion. |
| Rules | `src/interfaces.py`, `src/rules/` | Polymorphic scheduling constraints through `ISchedulingRule`. |
| Solver | `src/solver/` | Period-level backtracking and complete-system Cartesian product streaming. |
| Sorting and analytics | `src/sorting/`, `src/analytics/` | Part 3 metrics, schedule ranking, dashboard/report diagnostics. |
| Output | `src/output/` | Text and ICS formatting plus output file management. |

### Core Class Map

| Class or dataclass | Module | Main methods | Design role |
| --- | --- | --- | --- |
| `Evaluation`, `Exam`, `Project`, `Attendance` | `src/models/academic.py` | `requires_scheduling()` | Strategy pattern for deciding whether a course needs an exam slot. |
| `ProgramAffiliation` | `src/models/academic.py` | Data fields | Value object connecting courses to program/year/semester/requirement. |
| `Course` | `src/models/academic.py` | `add_affiliation()`, `needs_exam_slot()` | Domain entity for scheduled academic units. |
| `DateExclusion` | `src/models/scheduling.py` | `is_date_excluded()` | Value object for blocked dates or ranges. |
| `ExamPeriod` | `src/models/scheduling.py` | `add_exclusion()`, `is_date_valid()` | Domain entity for schedulable semester/term windows. |
| `BaseFactory`, `CourseFactory`, `PeriodFactory` | `src/parser/` | `build_all()`, `_build_one()` | Factory abstraction from parsed records to domain objects. |
| `ISchedulingRule` | `src/interfaces.py` | `is_valid()` | Common rule interface used by all solver constraints. |
| `AcademicConflictRule` | `src/rules/academic_conflict_rule.py` | `is_valid()` | V1 same-day conflict rule. |
| `ExamSpacingRule` | `src/rules/exam_spacing_rule.py` | `is_valid()`, `_has_spacing_conflict()` | Stage 3 requirements 2.1 and 2.2. |
| `AdvancedConstraintsRule` | `src/rules/advanced_constraints_rule.py` | `_check_daily_cap()`, `_check_mandatory_span()`, `_check_elective_conflicts()` | Stage 3 requirements 2.3, 2.4, and 2.5. |
| `AICopilotRule` | `src/rules/ai_copilot_rule.py` | `validate_rule_record()`, `is_valid()` | Enforces validated local AI copilot rules during scheduling. |
| `Scheduler` | `src/solver/period_scheduler.py` | `iter_assignments()`, `run_to_output()` | Exact period scheduler using conflict graph, components, and MRV search. |
| `CompleteSystemScheduler` | `src/solver/complete_scheduler.py` | `count_complete_systems()`, `stream_complete_systems()`, `write_complete_systems_auto()` | Complete yearly system generator and lazy stream provider. |
| `DiskAssignmentStore` | `src/solver/complete_scheduler.py` | `append()`, `__getitem__()`, `items_at()`, `close()` | Encapsulated storage for large component assignment sets. |
| `SchedulePrioritySorter` | `src/sorting/schedule_priority.py` | `sort()`, `score_tuple()` | Applies user-selected Part 3 sort priorities. |
| `ScheduleQualityScorer` | `src/sorting/schedule_priority.py` | `score()` | Calculates the five Stage 3 ranking metrics. |
| `ScheduleAnalyticsEngine` | `src/analytics/schedule_analytics.py` | `analyze()` | Builds deterministic dashboard/report diagnostics. |
| `SchedulerInputState` | `src/services/scheduler_input_state.py` | `write_selected_programs_file()`, `write_exam_dates_file()`, `write_constraints_file()` | Adapter that serializes UI state into the V1 file contract. |
| `SchedulerRunConfigBuilder` | `src/services/cli_run_service.py` | `build()` | Converts validated UI fields into a CLI run configuration. |
| `ProcessRunner` | `src/ui/process_runner.py` | `start()`, `send_input_line()`, `cancel()` | Owns local `QProcess` lifecycle and exposes Qt signals. |
| `MainWindow` | `src/ui/main_window.py` | `_start_cli_run()`, `_handle_stdout()`, `_request_next_schedule_batch()` | Application controller across UI, services, process, and output. |
| `InputPanel` | `src/ui/input_panel.py` | `show_*_page()`, `_build_config()` | Main menu shell and configuration widget composition. |
| `OutputView` | `src/ui/calendar_view.py` | `add_systems()`, `_apply_sort_priority()` | Schedule inspection, paging, sorting, and selected-schedule state. |

### OOP Principles Used

**Encapsulation**

Each layer hides its internal representation. For example,
`SchedulerInputState` owns selected programs, edited periods, and constraints,
then exposes only file-writing methods to the run-config builder.
`DiskAssignmentStore` hides whether assignments are still in memory or spooled
to a temporary binary file.

**Abstraction and polymorphism**

`ISchedulingRule` lets the solvers treat all constraints uniformly. The solver
calls `is_valid()` without depending on whether the rule is the V1 academic
conflict rule, Stage 3 spacing rule, advanced constraint rule, or AI copilot
rule.

**Inheritance**

The evaluation hierarchy uses `Evaluation` as the abstract base class, with
`Exam`, `Project`, and `Attendance` specializing scheduling behavior.
Factories inherit from `BaseFactory` to share object-building structure.

**Composition**

The UI is built by composing widgets rather than placing all logic in one
window. `InputPanel` composes file loading, program selection, calendar,
settings, dashboard, and AI copilot widgets. `MainWindow` composes services and
coordinates them through signals.

**Dataclass value objects**

Domain and transfer structures such as `ProgramAffiliation`, `ExamPeriod`,
`CliRunConfig`, `CompleteSystemResult`, and analytics rows are dataclasses.
This keeps data contracts readable and testable.

**Adapter pattern**

Services adapt the newer desktop UI to the original file-based backend:

- `SchedulerRunConfigBuilder` prepares CLI arguments.
- `SchedulerInputState` writes selected programs, edited dates, and constraints
  into runtime text files.
- `StdoutScheduleParser` and `ScheduleOutputDataAdapter` convert scheduler text
  back into UI view models.
- `ScheduleCalendarExportService` maps UI schedules into output-layer
  `ScheduledExam` records for ICS formatting.

**Dependency injection**

`MainWindow` accepts a `process_runner_factory`, and sorter/analytics classes
accept scorer dependencies. Tests can replace infrastructure without changing
production code.

### Design Patterns Applied

The implementation uses explicit Design Patterns to keep the backend
extensible and the UI integration readable:

| Design Pattern | Project Implementation | Design Purpose |
| --- | --- | --- |
| Strategy | `Evaluation` hierarchy and `ISchedulingRule` implementations | Encapsulates interchangeable scoring and constraint logic so schedules can be evaluated or filtered without changing the scheduler core. |
| Factory | `BaseFactory`, `CourseFactory`, `PeriodFactory`, `RoomFactory`, `TeacherFactory`, and related model factories | Centralizes object construction from parsed input records and keeps validation close to model creation. |
| Adapter | `SchedulerInputState`, `SchedulerRunConfigBuilder`, `StdoutScheduleParser`, and `ScheduleOutputDataAdapter` | Bridges PyQt6 UI state, CLI configuration, stdout parsing, and backend schedule models without coupling screens to solver internals. |

### Stage 3 OOP Alignment Verification

The Stage 3 implementation remains object-oriented and aligned with this
architecture:

- Constraint behavior is implemented as rule objects behind `ISchedulingRule`.
- UI threshold validation is isolated in `ConstraintSettingsPolicy`.
- Sort ranking is encapsulated by `SchedulePrioritySorter` and
  `ScheduleQualityScorer`.
- Dashboard diagnostics are encapsulated by `ScheduleAnalyticsEngine` and
  dashboard service classes.
- The UI does not instantiate solver classes directly. It builds a
  `CliRunConfig`, then `ProcessRunner` starts local `main.py` through
  `QProcess`.
- Local-only execution is enforced by architecture tests that block network and
  server imports.
- Lazy paging uses `CompleteSystemStream`, `ScheduleCache`, and
  `process_protocol.py`, keeping large products out of the UI event loop.

The main verification tests are:

```text
tests/architecture/test_architecture_imports.py
tests/architecture/test_network_isolation.py
tests/architecture/test_local_process_execution.py
tests/ui/test_import_boundaries.py
tests/services/test_scheduler_input_state.py
tests/sorting/test_schedule_priority.py
tests/solver/test_complete_system_scheduler.py
```

## Chapter 3: Code Readability And Commenting Standard

The codebase uses docstrings and short comments for architectural boundaries
and non-obvious implementation decisions. Comments should explain why a design
choice exists, not repeat the literal operation on the next line.

Current readability anchors:

- Module docstrings identify layer ownership, such as UI bootstrap, services,
  scheduling, sorting, and analytics.
- Rule class docstrings map classes to requirement numbers.
- `SchedulerInputState` comments explain why UI data is serialized into runtime
  files before calling the V1 backend.
- `ProcessRunner` and `MainWindow` comments mark the QProcess boundary.
- `CompleteSystemScheduler` helper objects document memory-bounded assignment
  storage and lazy complete-system streaming.
- `SchedulePrioritySorter` comments document the stable descending sort rule
  for all Part 3 criteria.

Reviewers should use this SDD together with `docs/layer_boundaries.md`,
`docs/qprocess_boundaries.md`, `docs/diagrams.md`, and
`docs/testing_and_validation.md`.
