# Testing And Validation

## Current Test Command

Run from the project root:

```powershell
python -m pytest -q -v -s -p no:cacheprovider
```

Use the pytest summary as the source of truth for the current number of tests
and the current runtime.

## Why Some Tests Are Slow

The runtime depends on the active input files. If the selected programs and
course catalog produce many valid schedules, integration tests that write
period-level output can take several seconds.

Use this command to inspect the current scale before running heavier tests:

```powershell
python main.py --mode complete-count
```

## Validation Strategy

The tests cover these layers:

- parser validation
- model behavior
- academic conflict rule behavior
- period scheduler correctness
- complete-system scheduler counting and writing
- workflow integration
- output manager behavior
- independent schedule validation

## Important Test Files

```text
tests/test_workflow.py
tests/parser/TestFileparser.py
tests/models/test_academic.py
tests/models/test_enums.py
tests/models/test_scheduling.py
tests/rules/test_academic_conflict_rule.py
tests/solver/test_new_scheduler_correctness.py
tests/solver/test_complete_system_scheduler.py
tests/solver/test_full_system_example.py
tests/solver/final_test.py
tests/solver/new_final_test.py
tests/output/test_output_manager.py
tests/output/test_schedule_sorter.py
```

## Correctness Checks

The current test suite checks that:

1. Only selected-program exam courses are scheduled.
2. Project and attendance courses are not scheduled.
3. Excluded dates are not used.
4. Same-program same-year obligatory conflicts are prevented.
5. Elective-elective exceptions are allowed.
6. Duplicate course IDs are rejected by the parser.
7. Period schedule counts multiply into the complete-system count.
8. Auto mode reports truncation when not all complete systems are written.
9. Output files are readable and follow the expected text format.

## Useful Manual Commands

Count complete systems:

```powershell
python main.py --mode complete-count
```

Write a limited complete-system sample:

```powershell
python main.py --mode complete-write --max-systems 1000
```

Run auto mode with the required 30-second budget:

```powershell
python main.py --mode auto --time-limit 30
```

Run only solver tests:

```powershell
python -m pytest tests/solver -q -v -s -p no:cacheprovider
```
