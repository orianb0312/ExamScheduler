# Offline Packaging Guide

This project can be delivered to a completely standalone Windows PC by building
an offline bundle on an internet-connected Windows PC, then running the bundled
installer script on the target PC.

The recommended first release format is:

```text
ExamScheduler-offline/
  app/                         project source, data, config, assets
  wheelhouse/                  Python wheels downloaded ahead of time
  vendor/
    python/
      python-installer.exe     optional but recommended
    ollama/
      OllamaSetup.exe          optional if target already has Ollama
      models/                  copied local Ollama model store
  install_offline.ps1
  verify_offline_install.ps1
  bundle_manifest.json
```

This approach intentionally does not freeze the app with PyInstaller. The UI
starts the scheduler backend through `QProcess` using `python main.py`; shipping
a portable Python runtime keeps that boundary working exactly as it works in
development.

## What Must Be Bundled

- Python runtime for Windows x64, unless the target PC already has a compatible
  Python installed.
- Runtime Python packages from `requirements-runtime.txt`.
- The project files: `gui_main.py`, `main.py`, `src/`, `data/`, `config.json`,
  and UI assets.
- Ollama for Windows, unless it is already installed on the target PC.
- The local Ollama model used by the AI Copilot:
  `llama3.1:8b-instruct-q4_K_M`.

Before redistributing a model, confirm that its license allows the way you plan
to distribute it. This is a release/legal checklist item, not a code issue.

## Build The Bundle On An Online PC

1. Install and test the app normally.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m pytest -q
   ```

2. Install Ollama on the build PC and pull the model.

   ```powershell
   ollama pull llama3.1:8b-instruct-q4_K_M
   ollama ls
   ```

3. Download the Python installer and Ollama installer to local files.

   Suggested filenames:

   ```text
   C:\Installers\python-installer.exe
   C:\Installers\OllamaSetup.exe
   ```

4. Build the offline bundle.

   ```powershell
   powershell -ExecutionPolicy Bypass -File packaging\build_offline_bundle.ps1 `
     -PythonInstaller C:\Installers\python-installer.exe `
     -OllamaInstaller C:\Installers\OllamaSetup.exe
   ```

5. Zip `dist\ExamScheduler-offline` and transfer that zip to the standalone PC.

   ```powershell
   Compress-Archive -Path dist\ExamScheduler-offline -DestinationPath dist\ExamScheduler-offline.zip -Force
   ```

## Install On The Offline PC

1. Extract the zip.
2. Run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File install_offline.ps1
   ```

The installer copies the app to `%LOCALAPPDATA%\ExamScheduler`, creates a local
virtual environment, installs wheels using `--no-index`, copies the Ollama model
store to `%USERPROFILE%\.ollama\models`, sets local AI environment variables,
and creates a desktop shortcut.

Run verification after installation:

```powershell
powershell -ExecutionPolicy Bypass -File verify_offline_install.ps1
```

Use the heavier model smoke test only when you want to confirm inference too:

```powershell
powershell -ExecutionPolicy Bypass -File verify_offline_install.ps1 -RunModelSmokeTest
```

## Notes

- Build wheels on the same OS and CPU architecture as the target PC. For this
  project that usually means Windows x64.
- Do not let the offline installer call `pip install` without `--no-index`, and
  do not run `ollama pull` on the target PC.
- Ollama stores models in `C:\Users\%username%\.ollama\models` by default, and
  also supports `OLLAMA_MODELS` when a different model location is needed.
- If the AI Copilot cannot start Ollama or load the model, the app fails closed:
  scheduling still works, but AI-created rules are not changed.
- The first model run may be slow while Ollama initializes the model.
