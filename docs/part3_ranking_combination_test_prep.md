# Part 3 Ranking Combination Test Prep

Source: `docs/version_34_corrected.md`, section B.3.

This note records the exact order expected from the multi-criteria schedule
ranking checks. The goal is to make the sorting behavior easy to review before
running the automated tests.

## Requirement Reading

Part 3 says that ranking criteria are chosen by the user and applied in the
order the user sets. Each selected metric is descending.

For these checks, the two relevant metrics are:

| Metric | Meaning | Direction |
|---|---|---|
| 3.1 | Minimum number of calendar days between two mandatory exams in the same program and year. | Descending |
| 3.5 | Maximum number of exams scheduled on the same date. | Descending |

The sorter must use lexicographic order: compare the first selected metric
first, use the next selected metric only when the earlier metric is tied, and do
not blend the scores into one weighted number.

## Shared Test Fixtures

The automated tests use small synthetic schedules with fixed names. Extra exams
on day 1 use different programs, so they change Metric 3.5 without changing the
mandatory gap for Metric 3.1.

| Schedule name | Metric 3.1 score | Metric 3.5 score |
|---|---:|---:|
| `wide_gap_crowded` | 6 | 3 |
| `wide_gap_medium` | 6 | 2 |
| `wide_gap_light` | 6 | 1 |
| `middle_gap_crowded` | 4 | 3 |
| `middle_gap_medium` | 4 | 2 |
| `tight_gap_heaviest` | 2 | 4 |

## Expected Ranking Orders

| Priority order | Exact expected result |
|---|---|
| `3.1`, then `3.5` | `wide_gap_crowded`, `wide_gap_medium`, `wide_gap_light`, `middle_gap_crowded`, `middle_gap_medium`, `tight_gap_heaviest` |
| `3.5`, then `3.1` | `tight_gap_heaviest`, `wide_gap_crowded`, `middle_gap_crowded`, `wide_gap_medium`, `middle_gap_medium`, `wide_gap_light` |

## Automated Assertions

The executable assertions live in `tests/sorting/test_schedule_priority.py`:

- `test_ranking_combination_fixture_scores_match_documented_metrics`
- `test_ranking_combinations_follow_documented_lexicographic_order`

Together they check that the fixture scores match this note and that flipping
the primary metric from 3.1 to 3.5 changes the final order exactly as documented.
