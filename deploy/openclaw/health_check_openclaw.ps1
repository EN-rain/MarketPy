param(
    [string]$BaseUrl = "http://localhost:8100"
)

$health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
$metrics = Invoke-WebRequest -Method Get -Uri "$BaseUrl/metrics"

Write-Host "Health:"
$health | ConvertTo-Json -Depth 10
Write-Host ""
Write-Host "Metrics (first 20 lines):"
$metrics.Content.Split("`n") | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
