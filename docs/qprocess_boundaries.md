# QProcess Boundaries

This document records which desktop actions may run in the PyQt UI process and
which actions must run through `QProcess`.

## Run Through QProcess

Use `QProcess` for scheduling work that can grow with the number of courses,
periods, or complete systems.

- `period` schedule generation
- `complete-count`
- `complete-write`
- `auto`
- lazy complete-system paging for the output screen

The UI starts these operations through `src/ui/process_runner.py`. The runner
launches `main.py` and keeps the solver outside the UI process.

## Safe To Run In The UI Process

These actions are small UI/state operations and should stay local:

- selecting or deselecting study programs
- opening selected-program course details
- filtering displayed courses by year or semester
- excluding or restoring a calendar day in the current loaded state
- editing an exam-period start or end date in the current loaded state

File loading/parsing currently runs in the UI flow because it is used as setup
before scheduling. If the real input files become large enough to freeze the
interface, the same `ProcessRunner` boundary can be extended for loading.

## Process Result Flow

The UI does not import the solver directly.

```text
InputPanel
  -> CliRunConfig
  -> ProcessRunner (QProcess)
  -> main.py
  -> workflow / solver
  -> stdout / stderr
  -> StdoutScheduleParser
  -> OutputView cache
```

For lazy paging, the process sends one page of schedule systems and then waits.
When the user asks for the next page, the UI sends `NEXT` to the same process.
When the user leaves the output screen, the UI sends `STOP`.

## Error Flow

- stdout carries schedule systems and batch markers.
- stderr carries small progress messages.
- QProcess errors are converted to readable UI messages by `ProcessRunner`.
- non-zero process exits are shown as output-screen errors.

This keeps the solution standalone and local without adding client-server
architecture.
