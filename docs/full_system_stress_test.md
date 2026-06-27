# Full System Stress Test

This opt-in QA test is intentionally not part of normal pytest runs. It starts the
real scheduler process, generates synthetic high-pressure data, samples CPU/RAM,
checks lazy pagination, exercises active AI rules, verifies reload-style process
termination, parses scheduler output, and builds deterministic dashboard analytics.

## Run from PowerShell

```powershell
$env:EXAMSCHEDULER_RUN_FULL_SYSTEM_STRESS = "1"
python -m pytest tests\system\test_full_system_stress.py -q -s
```

Reports are written to:

```text
performance_logs/full_system_stress_samples_<timestamp>.csv
performance_logs/full_system_stress_summary_<timestamp>.json
```

## Useful knobs

```powershell
$env:EXAMSCHEDULER_FULL_STRESS_COURSES = "24"
$env:EXAMSCHEDULER_FULL_STRESS_DAYS = "60"
$env:EXAMSCHEDULER_FULL_STRESS_MAX_SYSTEMS = "5000"
$env:EXAMSCHEDULER_FULL_STRESS_BATCHES = "5"
$env:EXAMSCHEDULER_FULL_STRESS_MAX_CHILD_RSS_MB = "2048"
$env:EXAMSCHEDULER_FULL_STRESS_MAX_GUI_RSS_MB = "1024"
$env:EXAMSCHEDULER_FULL_STRESS_MAX_SYSTEM_MEMORY_PERCENT = "98"
python -m pytest tests\system\test_full_system_stress.py -q -s
```

Clear the environment variables after the run if you do not want the stress test
enabled in the same terminal.
