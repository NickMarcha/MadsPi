Write-Host "Setting up Windows environment..."
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
Write-Host "Done. To activate later: .\.venv\Scripts\activate"
