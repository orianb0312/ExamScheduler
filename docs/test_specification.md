# ExamScheduler Test Specification Document

## 1. Purpose
This document defines the test specification and execution evidence for the ExamScheduler Version 1.0 project. It covers the complete automated pytest suite in the repository.

## 2. Scope
The scope includes parser and input validation, assessment type filtering, academic conflict validation, schedule generation, complete-system counting, output formatting, sorting, and end-to-end workflow behavior.

## 3. References
- Software Requirements Specification for ExamScheduler Version 1.0
- `data/V1.0CourseDB.txt`
- `data/V1.0 ExamDates.txt`
- `data/Programs.txt`
- `tests/`

## 4. Definitions and Abbreviations
- **SRS:** Software Requirements Specification
- **Moed:** Exam attempt period such as Aleph, Bet, or Gimel
- **Critical Conflict:** Two same-date exams sharing at least one program and study year, unless both courses are electives

## 5. Test Strategy
The project uses automated pytest tests at unit, integration, and system levels. The tests are grouped by responsibility so failures can be traced to a specific project layer.

## 6. Test Environment
- **Language:** Python
- **Test framework:** pytest
- **Primary test command:** `.\.venv\Scripts\python.exe -m pytest -q`
- **Test discovery command:** `.\.venv\Scripts\python.exe -m pytest --collect-only -q`

## 7. Test Data
- `data/V1.0CourseDB.txt`: course catalog
- `data/V1.0 ExamDates.txt`: exam-period definitions and exclusions
- `data/Programs.txt`: selected study programs
- Synthetic test objects for controlled tests

## 8. Defined Test Summary
| Area | Test file | Tests | Result |
|---|---|---:|---|
| File Parser and Input Validation | `tests/parser/TestFileparser.py` | 9 | Passed |
| Assessment Type Filtering | `tests/models/test_scheduling.py` | 7 | Passed |
| Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | 10 | Passed |
| Output Manager | `tests/output/test_output_manager.py` | 8 | Passed |
| Schedule Sorter | `tests/output/test_schedule_sorter.py` | 8 | Passed |
| Period Workflow | `tests/solver/final_test.py` | 1 | Passed |
| Complete-System Workflow | `tests/solver/new_final_test.py` | 2 | Passed |
| Complete-System Scheduler | `tests/solver/test_complete_system_scheduler.py` | 3 | Passed |
| Full-System Integration | `tests/solver/test_full_system_example.py` | 8 | Passed |
| Scheduler Correctness | `tests/solver/test_new_scheduler_correctness.py` | 5 | Passed |
| End-to-End Workflow | `tests/test_workflow.py` | 1 | Passed |

## 9. Defined Test Inventory
| # | Area | Test file | Test case | Purpose | Result |
|---:|---|---|---|---|---|
| 1 | Assessment Type Filtering | `tests/models/test_scheduling.py` | `test_filter_exam_courses_keeps_only_exam_courses` | Verifies filter exam courses keeps only exam courses. | Passed |
| 2 | Assessment Type Filtering | `tests/models/test_scheduling.py` | `test_filter_exam_courses_returns_empty_when_no_exam_courses` | Verifies filter exam courses returns empty when no exam courses. | Passed |
| 3 | Assessment Type Filtering | `tests/models/test_scheduling.py` | `test_filter_exam_courses_keeps_all_when_all_are_exam` | Verifies filter exam courses keeps all when all are exam. | Passed |
| 4 | Assessment Type Filtering | `tests/models/test_scheduling.py` | `test_filter_exam_courses_preserves_original_order` | Verifies filter exam courses preserves original order. | Passed |
| 5 | Assessment Type Filtering | `tests/models/test_scheduling.py` | `test_filter_exam_courses_empty_input_returns_empty` | Verifies filter exam courses empty input returns empty. | Passed |
| 6 | Assessment Type Filtering | `tests/models/test_scheduling.py` | `test_filter_exam_courses_does_not_mutate_input_list` | Verifies filter exam courses does not mutate input list. | Passed |
| 7 | Assessment Type Filtering | `tests/models/test_scheduling.py` | `test_filter_exam_courses_affiliations_not_required_for_filtering` | Verifies filter exam courses affiliations not required for filtering. | Passed |
| 8 | Output Manager | `tests/output/test_output_manager.py` | `test_config_loading_logic` | Verifies config loading logic. | Passed |
| 9 | Output Manager | `tests/output/test_output_manager.py` | `test_directory_auto_recovery` | Verifies directory auto recovery. | Passed |
| 10 | Output Manager | `tests/output/test_output_manager.py` | `test_empty_dict_handling` | Verifies empty dict handling. | Passed |
| 11 | Output Manager | `tests/output/test_output_manager.py` | `test_large_scale_master_export` | Verifies large scale master export. | Passed |
| 12 | Output Manager | `tests/output/test_output_manager.py` | `test_line_formatting_logic` | Verifies line formatting logic. | Passed |
| 13 | Output Manager | `tests/output/test_output_manager.py` | `test_none_input_handling` | Verifies none input handling. | Passed |
| 14 | Output Manager | `tests/output/test_output_manager.py` | `test_semester_without_terms_header` | Verifies semester without terms header. | Passed |
| 15 | Output Manager | `tests/output/test_output_manager.py` | `test_special_characters_support` | Verifies special characters support. | Passed |
| 16 | Schedule Sorter | `tests/output/test_schedule_sorter.py` | `test_boundary_dates` | Verifies boundary dates. | Passed |
| 17 | Schedule Sorter | `tests/output/test_schedule_sorter.py` | `test_case_insensitive_sorting` | Verifies case insensitive sorting. | Passed |
| 18 | Schedule Sorter | `tests/output/test_schedule_sorter.py` | `test_duplicate_objects` | Verifies duplicate objects. | Passed |
| 19 | Schedule Sorter | `tests/output/test_schedule_sorter.py` | `test_grouping_logic` | Verifies grouping logic. | Passed |
| 20 | Schedule Sorter | `tests/output/test_schedule_sorter.py` | `test_invalid_data_values` | Verifies invalid data values. | Passed |
| 21 | Schedule Sorter | `tests/output/test_schedule_sorter.py` | `test_large_input_scaling` | Verifies large input scaling. | Passed |
| 22 | Schedule Sorter | `tests/output/test_schedule_sorter.py` | `test_null_and_empty_inputs` | Verifies null and empty inputs. | Passed |
| 23 | Schedule Sorter | `tests/output/test_schedule_sorter.py` | `test_sorting_order` | Verifies sorting order. | Passed |
| 24 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_split_records` | Verifies split records. | Passed |
| 25 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_parse_program_line` | Verifies parse program line. | Passed |
| 26 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_parse_record` | Verifies parse record. | Passed |
| 27 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_parse_date_line` | Verifies parse date line. | Passed |
| 28 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_parse_period_record` | Verifies parse period record. | Passed |
| 29 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_valid_program_numbers` | Verifies valid program numbers. | Passed |
| 30 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_parse_user_selection` | Verifies parse user selection. | Passed |
| 31 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_parse_catalog_text_integration` | Verifies parse catalog text integration. | Passed |
| 32 | File Parser and Input Validation | `tests/parser/TestFileparser.py` | `test_parse_catalog_text_rejects_duplicate_course_numbers` | Verifies parse catalog text rejects duplicate course numbers. | Passed |
| 33 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_critical_conflict_same_year_program` | Verifies critical conflict same year program. | Passed |
| 34 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_elective_exception_allowed` | Verifies elective exception allowed. | Passed |
| 35 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_different_year_exception_allowed` | Verifies different year exception allowed. | Passed |
| 36 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_mixed_obligatory_and_elective_same_program_year_is_conflict` | Verifies mixed obligatory and elective same program year is conflict. | Passed |
| 37 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_different_program_same_year_same_date_is_allowed` | Verifies different program same year same date is allowed. | Passed |
| 38 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_same_program_year_different_dates_is_allowed` | Verifies same program year different dates is allowed. | Passed |
| 39 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_multi_affiliation_conflict_detected_on_any_shared_program_year` | Verifies multi affiliation conflict detected on any shared program year. | Passed |
| 40 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_is_valid_empty_attempt_state` | Verifies is valid empty attempt state. | Passed |
| 41 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_is_valid_single_course` | Verifies is valid single course. | Passed |
| 42 | Academic Conflict Rule | `tests/rules/test_academic_conflict_rule.py` | `test_same_date_without_shared_program_year_is_valid` | Verifies same date without shared program year is valid. | Passed |
| 43 | Period Workflow | `tests/solver/final_test.py` | `test_period_workflow_matches_current_default_inputs` | Verifies period workflow behavior for the Version 1.0 data set. | Passed |
| 44 | Complete-System Workflow | `tests/solver/new_final_test.py` | `test_complete_count_workflow_matches_current_default_inputs` | Verifies complete-system counting for the Version 1.0 data set. | Passed |
| 45 | Complete-System Workflow | `tests/solver/new_final_test.py` | `test_auto_complete_workflow_writes_limited_current_default_results` | Verifies bounded complete-system output and truncation reporting. | Passed |
| 46 | Complete-System Scheduler | `tests/solver/test_complete_system_scheduler.py` | `test_complete_system_count_multiplies_period_counts` | Verifies complete system count multiplies period counts. | Passed |
| 47 | Complete-System Scheduler | `tests/solver/test_complete_system_scheduler.py` | `test_complete_system_write_respects_explicit_limit` | Verifies that complete-system output respects a configured maximum number of systems. | Passed |
| 48 | Complete-System Scheduler | `tests/solver/test_complete_system_scheduler.py` | `test_complete_system_auto_writes_all_when_small` | Verifies complete-system output behavior when the result set is small. | Passed |
| 49 | Full-System Integration | `tests/solver/test_full_system_example.py` | `test_full_system_run_with_example_files_creates_non_empty_output_file` | Verifies full system run with example files creates non empty output file. | Passed |
| 50 | Full-System Integration | `tests/solver/test_full_system_example.py` | `test_full_system_counts_match_current_example_files` | Verifies expected schedule counts for the Version 1.0 example files. | Passed |
| 51 | Full-System Integration | `tests/solver/test_full_system_example.py` | `test_full_system_output_schedules_only_exam_courses_from_selected_programs` | Verifies full system output schedules only exam courses from selected programs. | Passed |
| 52 | Full-System Integration | `tests/solver/test_full_system_example.py` | `test_full_system_output_format_is_readable_and_valid` | Verifies full system output format is readable and valid. | Passed |
| 53 | Full-System Integration | `tests/solver/test_full_system_example.py` | `test_full_system_does_not_use_excluded_dates_from_example_periods` | Verifies full system does not use excluded dates from example periods. | Passed |
| 54 | Full-System Integration | `tests/solver/test_full_system_example.py` | `test_full_system_generated_period_schedules_have_no_conflicts` | Verifies full system generated period schedules have no conflicts. | Passed |
| 55 | Full-System Integration | `tests/solver/test_full_system_example.py` | `test_full_system_generated_schedules_pass_independent_validator` | Verifies full system generated schedules pass independent validator. | Passed |
| 56 | Full-System Integration | `tests/solver/test_full_system_example.py` | `test_full_system_run_finishes_within_required_time_limit` | Verifies that the full workflow completes within the required time limit. | Passed |
| 57 | Scheduler Correctness | `tests/solver/test_new_scheduler_correctness.py` | `test_validator_rejects_invalid_schedule_reasons` | Verifies validator rejects invalid schedule reasons. | Passed |
| 58 | Scheduler Correctness | `tests/solver/test_new_scheduler_correctness.py` | `test_new_scheduler_matches_brute_force_for_required_conflicts` | Verifies new scheduler matches brute force for required conflicts. | Passed |
| 59 | Scheduler Correctness | `tests/solver/test_new_scheduler_correctness.py` | `test_new_scheduler_matches_brute_force_for_multi_affiliation_conflicts` | Verifies new scheduler matches brute force for multi affiliation conflicts. | Passed |
| 60 | Scheduler Correctness | `tests/solver/test_new_scheduler_correctness.py` | `test_new_scheduler_matches_brute_force_for_elective_exception` | Verifies new scheduler matches brute force for elective exception. | Passed |
| 61 | Scheduler Correctness | `tests/solver/test_new_scheduler_correctness.py` | `test_every_emitted_schedule_passes_independent_validator` | Verifies every emitted schedule passes independent validator. | Passed |
| 62 | End-to-End Workflow | `tests/test_workflow.py` | `test_run_v1_workflow_processes_all_exam_periods` | Verifies run v1 workflow processes all exam periods. | Passed |

## 10. Executed Tests and Results
| Check | Command / Evidence | Result |
|---|---|---|
| Test Collection | `.\.venv\Scripts\python.exe -m pytest --collect-only -q` | 62 tests collected |
| Full Automated Suite | `.\.venv\Scripts\python.exe -m pytest -q` | 62 passed in 22.31 seconds |
| Complete-System Count | `.\.venv\Scripts\python.exe main.py --mode complete-count` | 4,900,186,368 complete systems |
| Period Workflow | `.\.venv\Scripts\python.exe main.py --mode period` | 1,084,824 period schedules across tested periods |
| Bounded Complete-System Output | `.\.venv\Scripts\python.exe main.py --mode complete-write --max-systems 1000` | 1,000 systems written; truncation reported |

## 11. Requirements Traceability Matrix
| Requirement | Verified behavior | Test evidence | Status |
|---|---|---|---|
| SRS 1.1 | Program selection allows up to five approved programs. | Parser and workflow tests | Covered |
| SRS 1.2 | Only Exam assessments are scheduled. | Assessment filtering and full-system output tests | Covered |
| SRS 1.2 | Same-date conflicts are rejected for the same program and year unless both courses are electives. | Academic conflict and scheduler-correctness tests | Covered |
| SRS 2.1 | The system reads course catalog, exam-period file, and selected-program file. | Parser and full-system integration tests | Covered |
| SRS 2.2 | Program identifiers are validated against approved program IDs. | Program ID parser tests | Covered |
| SRS 2.3 | Output is readable and grouped/sorted by semester and moed. | Output manager and schedule sorter tests | Covered |
| SRS 3.1-3.2 | Version 1.0 uses file-based input and text output. | Workflow and full-system tests | Covered |
| SRS 4.1-4.3 | Object-oriented components are separated by responsibility. | Parser, model, rule, solver, and output tests | Covered |
| SRS 5.1 | Schedule generation completes within the required time limit for the tested Version 1.0 runs. | Performance and workflow tests | Covered |
| Appendix A | Input separators, dates, semesters, moeds, and exclusions are handled correctly. | Parser and excluded-date tests | Covered |

## 12. Test Execution Instructions
Run the following command from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected result for the verified version: 62 tests passed, 0 failed.
