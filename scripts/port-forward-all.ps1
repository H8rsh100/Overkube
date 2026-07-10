<#
.SYNOPSIS
    Port-forward all Overkube services to local ports 9001-9010.
    Run this in a separate terminal before starting the traffic simulator.

.DESCRIPTION
    Spawns background kubectl port-forward processes for each service in
    the overkube namespace. Ports map to the SERVICE_PORT_MAP in traffic_sim.py.

.EXAMPLE
    .\scripts\port-forward-all.ps1
    # Then in another terminal:
    python cluster\load-gen\traffic_sim.py --all --duration 600
#>

$services = @{
    "api-gateway"           = 9001
    "user-service"          = 9002
    "inventory-service"     = 9003
    "order-processor"       = 9004
    "payment-service"       = 9005
    "search-service"        = 9006
    "auth-service"          = 9007
    "notification-service"  = 9008
    "recommendation-engine" = 9009
    "report-generator"      = 9010
}

$namespace = "overkube"
$jobs = @()

Write-Host "🔗 Starting port-forward for all Overkube services..." -ForegroundColor Cyan
Write-Host ""

foreach ($svc in $services.GetEnumerator()) {
    $name = $svc.Key
    $port = $svc.Value
    Write-Host "  → $name  localhost:$port → :8080" -ForegroundColor DarkGray

    $job = Start-Job -ScriptBlock {
        param($name, $namespace, $port)
        kubectl port-forward "svc/$name" "${port}:8080" -n $namespace
    } -ArgumentList $name, $namespace, $port

    $jobs += $job
}

Write-Host ""
Write-Host "✅ All port-forwards started. Press Ctrl+C to stop." -ForegroundColor Green
Write-Host "   Run traffic simulator:  python cluster\load-gen\traffic_sim.py --all --duration 600" -ForegroundColor Yellow
Write-Host ""

try {
    # Keep the script alive until Ctrl+C
    while ($true) { Start-Sleep -Seconds 5 }
}
finally {
    Write-Host ""
    Write-Host "Stopping all port-forwards..." -ForegroundColor Red
    $jobs | Stop-Job -PassThru | Remove-Job
    Write-Host "Done." -ForegroundColor DarkGray
}
