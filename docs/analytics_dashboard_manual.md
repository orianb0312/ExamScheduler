# ExamScheduler Dashboard User Manual

## Purpose

The Dashboard tab presents a professional read-only analytics viewport for the
ExamScheduler scheduling process. It does not generate schedules, change
constraints, rank schedules by itself, or write data back to the solver.

Use it to review high-level schedule scale, best-so-far quality, latest-batch
quality, study-gap risk, exam-load distribution, and deterministic insight
explanations.

## Navigation

1. Open the desktop application.
2. Load the course and exam-period files.
3. Select the study programs.
4. Generate schedules.
5. Open the `Dashboard` tab.
6. Review the KPI cards, load distribution chart, insight cards, and
   combinatorial pagination bar.

```text
Input shell
  -> Dashboard tab
    -> KPI cards
    -> Exam Load Distribution
    -> Deterministic Insight Cards
    -> Combinatorial Pagination
```

```text
+---------------- ExamScheduler Dashboard ----------------+
| Total Valid | Best So Far | Min Study Gap | Current Batch |
+----------------------------------------------------------+
| Exam Load Distribution chart | Insight and bottleneck     |
| by exam date                 | explanation cards          |
+----------------------------------------------------------+
| View Best Schedule       Chunk range       Generate Next  |
+----------------------------------------------------------+
```

## Dashboard Sections

### Header

The top-left header shows the existing project logo area and the product title
`ExamScheduler`. The dashboard intentionally has no sidebar and no top-right
notification/settings controls.

### KPI Cards

The first row contains four equal-width metric cards:

- Total Valid Schedules
- Best So Far
- Min Study Gap
- Current Batch Best

### Exam Load Distribution

The main left panel draws the exams-per-date chart using PyQt6 `QPainter`. This
matches the final local-only dashboard specification and avoids adding a
Matplotlib runtime dependency to the UI shell. The chart shows cyan glowing
bars, dashed grid lines, dynamic Y-axis ticks, hover values, and exam-date
labels.

### Deterministic Insight Cards

The right panel contains calculated insight cards:

- Winning Schedule Performance
- Chunk Bottleneck Analysis

These cards summarize why the current best schedule is strong or risky. The
text is deterministic Python formatting over calculated analytics values; no
language model generates or evaluates these insights.

### Combinatorial Pagination

The bottom bar shows the current chunk and schedule range, with action buttons:

- `View Best Schedule` returns to the generated schedule results screen and
  jumps to the current best-so-far schedule.
- `Generate Next 1,000` asks the active lazy scheduler process for the next
  result batch and then returns to the generated schedule results screen.

The Dashboard only emits user-intent signals. `MainWindow` owns the navigation
and process request, so the dashboard never runs the scheduling algorithm
directly.

## Usage Examples

### Inspect a generated chunk

Open the Dashboard tab and review the exam load distribution. Tall cyan bars
show dates with more scheduled exams.

### Explain schedule quality

Use the KPI cards and green insight card to explain the best schedule found so
far, the latest-batch winner, the tightest student-facing spacing, and the
highest daily exam load.

### Find bottlenecks

Use the orange bottleneck card to identify overload caused by constraint strain
inside the current chunk.

## Refresh Rules

The dashboard exposes reusable API methods:

- `update_metrics(total_schedules, fitness_score, min_study_gap, current_batch_score)`
- `update_chart_data(dates, values)`
- `update_insights(winning_text, bottleneck_text)`
- `set_pagination(chunk_number, start_index, end_index)`

The dashboard never asks the solver for new results.
