# ExamScheduler Documentation

This folder contains the current technical documentation for the ExamScheduler
project.

## Files

- `project_overview.md` - current system purpose, workflows, modes, and used files.
- `diagrams.md` - Mermaid diagrams for workflow, use cases, classes, and sequences.
- `diagram_exports/` - exported SVG, PNG, HTML, and PDF diagram files.
- `testing_and_validation.md` - test status, validation strategy, and useful commands.
- `organization_plan.md` - current structure notes and recommended cleanup steps.

## Current Main Entry Point

Run the app from the project root:

```powershell
python main.py --mode complete-count
python main.py --mode period
python main.py --mode auto --time-limit 30
```

The current default input files are:

```text
data/V1.0CourseDB.txt
data/V1.0 ExamDates.txt
data/Programs.txt
```
