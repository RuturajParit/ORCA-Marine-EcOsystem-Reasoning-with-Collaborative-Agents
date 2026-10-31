# Run from the ORCA project directory.

python -m venv .venv

if (Test-Path ".venv\Scripts\Activate.ps1") {
    .\.venv\Scripts\Activate.ps1
}

pip install -r requirements.txt

Write-Host ""
Write-Host "Testing Open-Meteo..."
python tests\test_open_meteo.py

Write-Host ""
Write-Host "Starting ORCA..."
python main.py
