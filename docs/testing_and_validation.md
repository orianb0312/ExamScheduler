# Testing And Validation

## Current Test Command

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Use the pytest summary as the source of truth for the current number of tests
and the current runtime.

Current verified result on July 1, 2026: the full pytest suite passed in the
local submission environment. Use the command output from the latest run as the
exact count and runtime.

`pytest.ini` keeps test discovery consistent, including capitalized files such
as `tests/parser/TestFileparser.py`.
`tests/conftest.py` gives pytest tests workspace-local temporary directories so
test output does not depend on Windows user-temp permissions.

## Why Some Tests Are Slow

The runtime depends on the active input files. If the selected programs and
course catalog produce many valid schedules, integration tests that write
period-level output can take several seconds.

The complete-system result space can be much larger than what is practical to
write to disk. For those cases, `complete-count` reports the exact full count
and `auto` writes as many complete systems as fit inside the configured time
budget while still reporting whether the output was truncated.

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
- Part 3 constraint input prep and Req 2.2 mock-data checks

## Important Test And Documentation Files

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
tests/constraints/test_part3_k_input_validation.py
tests/constraints/test_part3_req_2_2_mock_data.py
tests/fixtures/part3_req_2_2_mock_pairs.json
docs/test_specification.md
docs/part3_constraint_unit_test_prep.md
docs/ExamScheduler_Test_Specification_v1_0.docx
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
8. Complete-system counts are exact, even when full output is too large to write.
9. Auto mode reports truncation when not all complete systems are written.
10. Output files are readable and follow the expected text format.
11. Part 3 k validation rejects zero and negative values for requirements
    2.1, 2.2, 2.4, and 2.5.
12. Part 3 k validation accepts zero for requirement 2.3 and rejects negative
    values.
13. Req 2.2 mock data covers mandatory-mandatory, mandatory-elective, and
    elective-elective exam pairs with exact-k and under-k boundaries.

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
.\.venv\Scripts\python.exe -m pytest tests/solver -q
```
