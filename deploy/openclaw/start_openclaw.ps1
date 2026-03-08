param(
    [string]$ProjectRoot = ".",
    [int]$Port = 8100
)

Set-Location $ProjectRoot
$env:PYTHONPATH = $ProjectRoot
python -m uvicorn backend.app.openclaw.main:app --host 0.0.0.0 --port $Port
