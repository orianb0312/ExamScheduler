# Real AI Copilot Model Benchmark

Use this benchmark for the actual model decision. Unlike
`ai_model_benchmark.py`, this runner goes through the production
`AICopilotWorker` path:

- input sanitization
- deterministic routing
- production prompt
- real Ollama invocation
- strict production JSON/schema validation
- Qt `constraint_ready` and `response_ready` signals
- blocked-request audit reasons from `security_log.txt`

That makes the result representative of what the desktop app will do.

The fixture is intentionally QA/red-team oriented. It mixes normal scheduling
requests with prompt-injection attempts, protected base-rule tampering,
unsupported scheduling details, off-topic bait, ambiguous dates, and duplicate
rule checks. It also includes a `model_semantic_supported` bucket with awkward
but valid scheduling requests that should still reach Ollama, so the benchmark
continues to compare model value, time, and precision. A model/package candidate
should survive these cases without turning hostile or unrelated text into
scheduling rules.

## Run

Run both models with the production worker timeout:

```powershell
python tools\ai_copilot_real_benchmark.py `
  --models llama3.1:8b-instruct-q4_K_M qwen3:4b `
  --repeats 3
```

`qwen3:*` models use the app's Qwen3 profile: a shorter classifier prompt is
prefixed with `/no_think`, the user request is passed as delimited plain text,
and the Ollama command omits `--hidethinking` because this Ollama/Qwen3
combination can suppress the final answer when that flag is enabled. The worker
strips Qwen's visible `Thinking...` prefix before normal JSON validation.

If `ollama` is not on `PATH`, either omit `--ollama` and let the worker use the
same resolution logic as the app, or pass the full path:

```powershell
python tools\ai_copilot_real_benchmark.py `
  --ollama "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" `
  --models llama3.1:8b-instruct-q4_K_M qwen3:4b `
  --repeats 3
```

Useful targeted runs:

```powershell
python tools\ai_copilot_real_benchmark.py --category supported_fix_date --repeats 1
python tools\ai_copilot_real_benchmark.py --category model_semantic_supported --repeats 1
python tools\ai_copilot_real_benchmark.py --category safety --repeats 1
python tools\ai_copilot_real_benchmark.py --case-id fix_date_physics_iso --repeats 1
```

## Outputs

Reports are written under:

```text
outputs/ai_copilot_real_benchmark/
```

Use the Markdown summary for the decision, then inspect the raw CSV for failed
cases. The raw CSV includes emitted constraints, UI responses, blocked audit
reasons, raw model stdout, and raw model stderr.

## Decision Rule

Prefer the smaller model only if it is close to the baseline on:

- total score
- exact/action pass count
- blocked case correctness
- supported rule precision
- average and worst latency

For the installer decision, the smaller model should keep at least 90-95 percent
of the baseline quality and have no safety regressions.
