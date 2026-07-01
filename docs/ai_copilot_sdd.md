# Local AI Copilot SDD Notes

## Responsibility

The Local AI Copilot is an offline natural-language constraint parser. It never
creates schedules, ranks schedules, writes directly to the scheduling database,
or changes base academic rules. It proposes validated JSON rule configuration
events that the user must confirm before they are persisted.

## Runtime Flow

1. The PyQt6 sidebar captures the coordinator request.
2. `AICopilotWorker` validates and sanitizes the text before inference.
3. The local Ollama model runs through `QProcess` with JSON mode enabled.
4. The worker parses the model response with strict JSON/schema validation.
5. `InputPanel` shows a confirmation dialog with the current AI rules and the
   proposed JSON change.
6. Confirmed events are emitted through Qt signals to `MainWindow`.
7. `MainWindow` writes only chatbot-owned rules to `data/active_ai_rules.json`.
8. The CLI workflow passes that absolute path to the solver.
9. `AICopilotRule` reloads and revalidates the JSON before enforcement.

## Guardrails

- Layer 1 blocks unsafe Unicode, HTML/script tags, SQL-like commands, code
  snippets, persona changes, system-prompt leakage, and Red-Team wording.
- User text is capped at 250 characters before local model execution.
- Layer 2 uses a hardcoded system prompt that treats user text as untrusted JSON
  data and limits outputs to supported scheduling-rule objects.
- Layer 3 rejects invalid JSON, duplicate keys, unknown schema keys, unsupported
  actions, non-English generated rule values, unsafe parameters, and duplicate
  active rules.
- Local model timeout, missing model, and memory/OOM failures fail closed and do
  not change manual settings or persisted AI rules.

## User Interface States

- Idle: input and Send button are enabled.
- Processing: input is locked and the sidebar shows `Processing request...`.
- Confirmation: a modal diff view shows current AI rules and the proposed JSON.
- Applied: the sidebar shows the created or reverted `ai_rule_*` item.
- Blocked/fallback: a generic safe message is shown and the raw blocked request
  is logged to `security_log.txt`.

## CLI Export

File-based mode can export one already-parsed AI JSON object as a validated AI
rules file:

```powershell
python main.py --ai-constraint-json-file parsed_constraint.json --export-ai-constraint-file data/active_ai_rules.json
```

The export path is resolved absolutely and the resulting file uses the same
schema consumed by the solver.
