Write-Host "Setting up Windows environment..."

# Check if virtual environment already exists
if (Test-Path ".venv") {
    Write-Host "Virtual environment already exists, removing old one..."
    Remove-Item -Recurse -Force ".venv"
}

# Create new virtual environment
Write-Host "Creating virtual environment..."
python -m venv .venv

# Activate virtual environment
Write-Host "Activating virtual environment..."
.\.venv\Scripts\activate

# Try to upgrade pip, but don't fail if it doesn't work
Write-Host "Upgrading pip..."
try {
    python -m pip install --upgrade pip --user
} catch {
    Write-Host "Pip upgrade failed, continuing with existing version..."
}

# Install requirements
Write-Host "Installing requirements..."
pip install -r requirements.txt

Write-Host "Done. To activate later: .\.venv\Scripts\activate"
