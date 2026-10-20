# Local setup on Windows (PowerShell)

These steps run the app, the tests and the smoke test on a Windows laptop. They need **Python 3.10–3.13**
and **Git**. Nothing here changes machine-wide settings.

> **Why the virtual environment lives outside the project folder:** if the project sits inside a
> OneDrive-synced folder (e.g. `Desktop`), OneDrive would try to sync thousands of package files.
> Keeping the environment in `%USERPROFILE%\.venvs` avoids that. The `.gitignore` also excludes any
> local `.venv`.

## 1. Check prerequisites

```powershell
python --version      # or: py --version
git --version
```

If `python` opens the Microsoft Store or is not found, use the Python launcher (`py`), your Anaconda
Prompt, or install Python from https://www.python.org/downloads/windows/ (tick "Add python.exe to PATH").

## 2. Open the project folder

```powershell
cd "$env:USERPROFILE\OneDrive\Desktop\E-commerce"
```

## 3. Create the virtual environment (once)

```powershell
$VENV = "$env:USERPROFILE\.venvs\ecom-pricing"
python -m venv $VENV
& "$VENV\Scripts\python.exe" -m pip install --upgrade pip
& "$VENV\Scripts\python.exe" -m pip install -r requirements-dev.txt
```

*Anaconda alternative:* `conda create -n ecom-pricing python=3.12 -y`, then `conda activate ecom-pricing`
and `pip install -r requirements-dev.txt`. Replace `& "$VENV\Scripts\python.exe"` with `python` below.

Calling the environment's `python.exe` directly means you never need to run `Activate.ps1`, so no
PowerShell execution-policy change is required. (If you prefer activating, run
`& "$VENV\Scripts\Activate.ps1"`; if PowerShell blocks it, keep using the direct path instead.)

## 4. Run the app

```powershell
& "$VENV\Scripts\python.exe" -m streamlit run app.py
```

Streamlit prints a local URL (normally http://localhost:8501) and opens it in your browser.
Press `Ctrl+C` in PowerShell to stop it.

## 5. Run the quality checks

```powershell
& "$VENV\Scripts\python.exe" -m pytest                 # unit + UI tests
& "$VENV\Scripts\python.exe" -m ruff check .           # lint
& "$VENV\Scripts\python.exe" scripts\smoke_test.py     # renders every page + starts a server
```

## 6. Regenerate the synthetic data (optional)

```powershell
& "$VENV\Scripts\python.exe" scripts\generate_data.py            # seed 42, identical to the committed CSV
& "$VENV\Scripts\python.exe" scripts\generate_data.py --seed 7   # a different reproducible draw
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: pricing_intel` when running a script | Run commands from the project root folder. |
| `streamlit` is not recognised | Use `& "$VENV\Scripts\python.exe" -m streamlit …` as shown above. |
| Port 8501 already in use | `… -m streamlit run app.py --server.port 8502` |
| Antivirus or firewall prompt on first run | Streamlit serves on localhost only; allowing private networks is enough. |
| Slow first start | The first run builds caches; later reruns are fast. |
