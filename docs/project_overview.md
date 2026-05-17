# Project Overview

## Purpose

ExamScheduler reads university course, exam-period, and selected-program files,
filters the relevant exam courses, generates valid exam schedules, and writes or
counts complete exam systems.

The current implementation supports both:

- period-level schedules, for one exam period at a time
- complete yearly systems, calculated as the Cartesian product of period-level schedules

## Result Counts

Result counts are data-dependent. The current values should be calculated from
the active input files instead of written into the documentation.

Default input files:

```text
data/V1.0CourseDB.txt
data/V1.0 ExamDates.txt
data/Programs.txt
```

To get the current count:

```powershell
python main.py --mode complete-count
```

The command reports:

```text
Period #0: <course count> courses, <period schedule count> period schedules
Period #1: <course count> courses, <period schedule count> period schedules
...
Complete systems: <product of all period schedule counts>
```

The complete-system count is:

```text
period_1_schedule_count * period_2_schedule_count * ... * period_n_schedule_count
```

## Main Modes

Run commands from the project root.

### Period Mode

```powershell
python main.py --mode period
```

Generates period-level schedules and writes them to the output file configured
in `config.json`.

### Complete Count Mode

```powershell
python main.py --mode complete-count
```

Counts complete systems without writing all of them.

Use this first when the result count may be huge.

### Complete Write Mode

```powershell
python main.py --mode complete-write --max-systems 1000
```

Writes complete systems. Use `--max-systems` when the full result count is too
large to write safely.

### Auto Mode

```powershell
python main.py --mode auto --time-limit 30
```

Counts all complete systems, then writes as many complete systems as fit within
the time limit. If the system is too large, output is truncated but the full
count is still reported.

## Runtime Code Path

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

## Important Runtime Files

```text
main.py
config.json
data/V1.0CourseDB.txt
data/V1.0 ExamDates.txt
data/Programs.txt
src/workflow.py
src/interfaces.py
src/models/academic.py
src/models/scheduling.py
src/models/enums.py
src/parser/file_parser.py
src/parser/IParser.py
src/parser/base_factory.py
src/parser/course_factory.py
src/parser/period_factory.py
src/rules/academic_conflict_rule.py
src/solver/period_scheduler.py
src/solver/complete_scheduler.py
src/output/base_output_manager.py
src/output/output_manager.py
src/output/output_models.py
```

## Scheduling Rule

The active scheduling rule is `AcademicConflictRule`.

Two exams may not be scheduled on the same date if they belong to the same
program and year and at least one of the two courses is obligatory. If both
courses are electives for that same cohort, the conflict is allowed.

## Algorithm Summary

The period scheduler:

1. Builds the list of valid dates for the exam period.
2. Builds a conflict graph between courses.
3. Splits the graph into connected components.
4. Solves each component with backtracking and MRV ordering.
5. Combines independent component results using Cartesian product.
6. Streams schedules to the output file.

The complete scheduler:

1. Builds period-level schedule sets for all selected periods.
2. Counts complete systems by multiplying period schedule counts.
3. Optionally streams complete systems to the output file.
4. In auto mode, stops writing near the time limit and reports truncation.
