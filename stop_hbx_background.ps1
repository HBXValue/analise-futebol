$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $projectRoot "runserver.pid"

if (Test-Path $pidFile) {
    try {
        $pidValue = [int](Get-Content $pidFile -ErrorAction Stop | Select-Object -First 1)
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    } catch {
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

Get-Process -Name waitress-serve,python,powershell -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Path -like "*New project*" -or $_.Path -like "*.venv\\Scripts\\python.exe"
    } |
    Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Servidor HBX finalizado."
