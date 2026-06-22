# ExamScheduler Documentation

This folder contains the current technical documentation for the ExamScheduler
project.

## Files

- `project_overview.md` - current system purpose, workflows, modes, and used files.
- `diagrams.md` - Mermaid diagrams for workflow, use cases, classes, and sequences.
- `diagram_exports/` - exported SVG, PNG, HTML, and PDF diagram files.
- `testing_and_validation.md` - test status, validation strategy, and useful commands.
- `test_specification.md` - formal Version 1.0 test specification and execution results.
- `part3_constraint_unit_test_prep.md` - Part 3 constraint edge-case plan,
  Req 2.2 mock data, and k-input expectations.
- `ExamScheduler_Test_Specification_v1_0.docx` - Word version of the formal test specification.
- `organization_plan.md` - current structure notes and recommended cleanup steps.
- `layer_boundaries.md` - ownership rules for PyQt6 UI, services/adapters, and v1.0 logic.

## Current Main Entry Point

Run the app from the project root:

```powershell
python main.py --mode complete-count
python main.py --mode period
python main.py --mode auto --time-limit 30
```

Standalone PyQt6 desktop entry point:

```powershell
.\.venv\Scripts\python.exe gui_main.py
```

The current default input files are:

```text
data/V1.0CourseDB.txt
data/V1.0 ExamDates.txt
data/Programs.txt
```
