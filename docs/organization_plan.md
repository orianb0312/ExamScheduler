# Organization Plan

This document describes the current organization state and the recommended
cleanup steps.

## Current Main Structure

```text
ExamScheduler/
├── main.py
├── config.json
├── README.md
├── schedule_sorter.py
├── data/
├── docs/
├── src/
│   ├── workflow.py
│   ├── interfaces.py
│   ├── models/
│   ├── parser/
│   ├── rules/
│   ├── solver/
│   ├── output/
│   ├── validation/
│   └── archive/
└── tests/
    ├── models/
    ├── parser/
    ├── rules/
    ├── solver/
    └── output/
```

## Current Runtime Path

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

## Keep

These files are part of the current app path:

```text
main.py
config.json
data/
src/workflow.py
src/interfaces.py
src/models/
src/parser/
src/rules/academic_conflict_rule.py
src/solver/period_scheduler.py
src/solver/complete_scheduler.py
src/output/base_output_manager.py
src/output/output_manager.py
src/output/output_models.py
src/validation/schedule_validator.py
tests/
docs/
```

## Cleanup Candidates

Generated or temporary files:

```text
__pycache__/
.pytest_cache/
outputs/
test_master_output/
test_config.json
```

Old archived scheduler code:

```text
src/archive/
```

Root-level legacy helper:

```text
schedule_sorter.py
```

`schedule_sorter.py` is not used by the current `main.py` runtime path. If it
is kept, consider moving it to:

```text
src/output/schedule_sorter.py
```

and updating:

```text
tests/output/test_schedule_sorter.py
```

## Important Gitignore Note

If `.gitignore` contains a broad rule like:

```text
output/
```

it may accidentally ignore:

```text
src/output/
tests/output/
```

Recommended safer ignore rules:

```text
/output/
/outputs/
/test_master_output/
```

The leading slash makes the rule apply only to root-level generated folders.

## Optional Naming Improvements

Recommended future renames:

```text
src/parser/IParser.py -> src/parser/parser_interface.py
tests/parser/TestFileparser.py -> tests/parser/test_file_parser.py
tests/solver/final_test.py -> tests/solver/test_period_workflow_default_inputs.py
tests/solver/new_final_test.py -> tests/solver/test_complete_workflow_default_inputs.py
```

Recommended class rename:

```text
src/solver/period_scheduler.py
class Scheduler -> class PeriodScheduler
```

This would make imports clearer:

```python
from src.solver.period_scheduler import PeriodScheduler
```

## Final Target Structure

```text
ExamScheduler/
├── main.py
├── config.json
├── README.md
├── data/
├── docs/
├── src/
│   ├── workflow.py
│   ├── interfaces.py
│   ├── models/
│   ├── parser/
│   ├── rules/
│   ├── solver/
│   │   ├── period_scheduler.py
│   │   └── complete_scheduler.py
│   ├── output/
│   │   ├── base_output_manager.py
│   │   ├── output_manager.py
│   │   └── output_models.py
│   └── validation/
└── tests/
    ├── models/
    ├── parser/
    ├── rules/
    ├── solver/
    ├── output/
    └── test_workflow.py
```

