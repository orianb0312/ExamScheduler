# ExamScheduler

ExamScheduler is a Python exam-scheduling tool for generating and counting valid
university exam schedules from file-based inputs.

The project supports:

- period-level schedule generation
- complete yearly system counting
- limited complete-system writing
- auto writing within a time limit

## Quick Start

Run commands from the project root.

Count all complete systems without writing them:

```powershell
python main.py --mode complete-count
```

Generate period-level schedules:

```powershell
python main.py --mode period
```

Write as many complete systems as fit in the time limit:

```powershell
python main.py --mode auto --time-limit 30
```

Write a limited complete-system sample:

```powershell
python main.py --mode complete-write --max-systems 1000
```

## Default Files

```text
data/V1.0CourseDB.txt
data/V1.0 ExamDates.txt
data/Programs.txt
config.json
```

The output path is configured in `config.json`.

## Counting Results

Result counts depend on the current input files. To get the exact current
counts, run:

```powershell
python main.py --mode complete-count
```

The command prints each period's course count, each period's schedule count,
and the total complete-system count.

Conceptually, the complete-system count is:

```text
period_1_schedule_count * period_2_schedule_count * ... * period_n_schedule_count
```

## Project Flow

```text
main.py
  -> src/workflow.py
    -> src/parser/file_parser.py
    -> src/parser/course_factory.py
    -> src/parser/period_factory.py
    -> src/rules/academic_conflict_rule.py
    -> src/solver/period_scheduler.py
    -> src/solver/complete_scheduler.py
    -> src/output/output_manager.py
```

## Main Modules

- `src/workflow.py` - connects parsing, filtering, scheduling, counting, and output.
- `src/parser/file_parser.py` - reads and validates input files.
- `src/models/` - domain models for courses, periods, affiliations, and enums.
- `src/rules/academic_conflict_rule.py` - V1.0 conflict rule.
- `src/solver/period_scheduler.py` - exact period-level scheduler.
- `src/solver/complete_scheduler.py` - complete-system counter and writer.
- `src/output/` - output configuration and text output manager.
- `src/validation/schedule_validator.py` - independent validation used by tests.

## Scheduling Rule

Two exams cannot be scheduled on the same date when they share the same program
and study year, unless both courses are electives for that shared cohort.

## Tests

Run all tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The test count may change as files are added or removed, so use the pytest
summary as the source of truth.

## Documentation

Detailed documentation is in `docs/`:

- `docs/project_overview.md`
- `docs/diagrams.md`
- `docs/testing_and_validation.md`
- `docs/test_specification.md`
- `docs/ExamScheduler_Test_Specification_v1_0.docx`
- `docs/organization_plan.md`
