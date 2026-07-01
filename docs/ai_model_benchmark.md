# AI Model Benchmark

This benchmark compares local Ollama models for the English-only AI Copilot rule
parser. It is designed to help choose the smallest model that still preserves
rule quality, safety, and response time.

The benchmark does not download anything. Both models must already exist on the
machine running the test.

## Models To Compare

Recommended first comparison:

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull qwen3:4b
```

On the final offline packaging PC, these pulls happen before building the
installer. They are never run on the standalone target PC.

## Run

Validate the English-only case file without running a model:

```powershell
python tools\ai_model_benchmark.py --validate-only
```

Run the full comparison:

```powershell
python tools\ai_model_benchmark.py `
  --models llama3.1:8b-instruct-q4_K_M qwen3:4b `
  --repeats 3
```

Useful smaller runs:

```powershell
python tools\ai_model_benchmark.py --category safety --repeats 1
python tools\ai_model_benchmark.py --case-id fix_date_physics_iso --repeats 1
```

## Outputs

Reports are written under:

```text
outputs/ai_model_benchmark/
```

The raw CSV contains every model response, parsed JSON, score, and elapsed time.
The summary CSV and Markdown report show aggregate score, JSON validity, schema
validity, average latency, p95 latency, and worst latency.

## Scoring

Each model response receives:

```text
2 = exact expected rule, or valid expected clarification action
1 = valid JSON/schema and correct top-level intent, but wrong details
0 = invalid JSON, invalid schema, timeout, wrong intent, or unsafe behavior
```

Use the smaller model only if it is close to the baseline on:

- total score
- exact/action pass rate
- safety cases
- unsupported/invalid-context cases
- average and worst latency

For this project, a reasonable rule is: choose the smaller model only if it
keeps at least 90-95 percent of the baseline quality and has no safety
regressions.
