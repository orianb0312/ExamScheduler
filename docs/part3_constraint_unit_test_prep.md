# Part 3 Constraint Unit Test Prep

Source: Part 3 requirements document, section B.2.

This note records the unit-test parameters and expected behavior for constraints
2.1 through 2.5. The cases are written as prep for the threshold rules, with
input validation kept separate from future solver enforcement.

## Requirement Reading

| Req | Constraint | k rule | Expected boundary |
|---|---|---|---|
| 2.1 | Minimum days between two mandatory exams in the same program and year. | Positive whole number. | Exactly k days is valid; fewer than k days is invalid. |
| 2.2 | Minimum days between any two exams in the same program and year, where each exam may be mandatory or elective. | Positive whole number. | Mandatory-mandatory, mandatory-elective, and elective-elective pairs all use the same boundary. |
| 2.3 | Maximum number of conflicts between two elective courses in the same program, per program. | Non-negative whole number. | k = 0 is valid and means no elective-elective conflicts are allowed. |
| 2.4 | Minimum days between the first and last mandatory exams in the same program, year, and moed. | Positive whole number. | Exactly k days between first and last is valid; fewer than k is invalid. |
| 2.5 | Maximum number of exams scheduled on the same day. | Positive whole number. | Exactly k exams on one day is valid; k + 1 exams is invalid. |

Day counts include Saturdays and holidays, as stated in the Part 3 wording.

## Req 2.2 Mock Data

The fixture file is `tests/fixtures/part3_req_2_2_mock_pairs.json`.

All mock pairs use program `83101`, year `2`, semester `FALL`, and exam
courses. The fixture covers:

| Pair type | Boundary cases |
|---|---|
| mandatory-mandatory | One case exactly k days apart; one case under k. |
| mandatory-elective | One case exactly k days apart; one case under k. |
| elective-elective | One case exactly k days apart; one case under k. |

Expected behavior for Req 2.2:

- A pair with `gap_days >= k` is accepted.
- A pair with `gap_days < k` is rejected.
- The requirement applies even when both exams are electives.

## Isolated k Input Tests

The isolated validation script is
`tests/constraints/test_part3_k_input_validation.py`.

Expected behavior:

| Req | Raw k | Expected |
|---|---|---|
| 2.1 | `0`, `-1` | Rejected. |
| 2.2 | `0`, `-1` | Rejected. |
| 2.3 | `0` | Accepted. |
| 2.3 | `-1` | Rejected. |
| 2.4 | `0`, `-1` | Rejected. |
| 2.5 | `0`, `-1` | Rejected. |

These tests call the pure `ConstraintSettingsPolicy`, so they do not depend on
GUI state, file parsing, or scheduler output.

## Edge Cases To Carry Into Solver Tests

| Req | Edge cases |
|---|---|
| 2.1 | mandatory-mandatory exact k; mandatory-mandatory under k; different program or year does not trigger the rule. |
| 2.2 | mandatory-mandatory, mandatory-elective, and elective-elective exact k and under k; different program or year does not trigger the rule. |
| 2.3 | zero conflicts with k = 0; one elective-elective conflict with k = 0; exactly k conflicts; k + 1 conflicts; conflicts counted per program. |
| 2.4 | first-to-last mandatory span exactly k; span under k; one mandatory exam in scope should not fail by itself. |
| 2.5 | exactly k exams on a day; k + 1 exams on a day; exams spread across dates are counted per date. |
