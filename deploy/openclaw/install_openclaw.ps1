param(
    [string]$ProjectRoot = "."
)

Set-Location $ProjectRoot
python -m pip install -r requirements.txt
Write-Host "OpenClaw dependencies installed."
