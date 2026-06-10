# Layer Boundaries

This project keeps the PyQt6 desktop UI separate from the existing v1.0
parsing, scheduling, and output code.

## UI Layer

The UI layer owns widgets, layouts, signals, styles, and screen navigation.

```text
gui_main.py
src/ui/
```

UI modules may import `src.services` and other `src.ui` modules. They should not
import the v1.0 parser, workflow, scheduler, domain model, rule, output, or
validation modules directly.

## UI Services And Adapters

Services prepare data for the UI and adapt UI requests to the existing v1.0
application path.

```text
src/services/cli_run_service.py
src/services/file_loading_service.py
src/services/file_selection_service.py
src/services/input_data_service.py
src/services/program_selection_policy.py
src/services/schedule_output_service.py
src/services/scheduler_input_state.py
```

These modules must stay free of PyQt6 imports. A service may call v1.0 modules
when it is acting as an adapter, such as `ExistingFileParserAdapter` or
`V1CliRunAdapter`.

## Process Protocol

The UI and `main.py` share a tiny text protocol for lazy schedule paging.
It lives outside the UI and service layers so both sides can import it without
reversing dependencies.

```text
src/process_protocol.py
```

The protocol contains markers such as `NEXT`, `STOP`, and the batch-end marker.
It does not import PyQt6 or scheduling code.

## Existing V1.0 Application And Domain Layer

The v1.0 layer owns parsing, domain objects, scheduling rules, schedule
generation, validation, and output.

```text
main.py
src/workflow.py
src/interfaces.py
src/models/
src/parser/
src/rules/
src/solver/
src/output/
src/validation/
```

This layer must not import `src.ui`, `src.services` UI helpers, or `PyQt6`.

## Dependency Direction

```text
PyQt6 UI -> services/adapters -> v1.0 application/domain
```

The reverse direction is intentionally blocked. Widgets collect user input,
show state, and emit signals; services handle validation, parsing adapters,
command construction, selection policy, and output-text adaptation.

Long-running scheduling work crosses this boundary through `QProcess`, not by
calling scheduler classes from widgets. See `docs/qprocess_boundaries.md` for
the chosen process boundaries.
