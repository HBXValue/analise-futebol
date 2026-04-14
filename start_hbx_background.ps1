$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverScript = Join-Path $projectRoot "start_lan_server.ps1"
$pidFile = Join-Path $projectRoot "runserver.pid"
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $serverScript)) {
    Write-Error "Script do servidor nao encontrado: start_lan_server.ps1"
    exit 1
}

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python da virtualenv nao encontrado em .venv\\Scripts\\python.exe"
    exit 1
}

Write-Host "Aplicando migracoes pendentes..."
& $pythonExe manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha ao aplicar migracoes. O servidor nao foi iniciado."
    exit $LASTEXITCODE
}

if (Test-Path $pidFile) {
    try {
        $existingPid = [int](Get-Content $pidFile -ErrorAction Stop | Select-Object -First 1)
        $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existingProcess) {
            Write-Host "Servidor HBX ja esta em execucao no processo $existingPid."
            exit 0
        }
    } catch {
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

Get-Process -Name waitress-serve,python,powershell -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Path -like "*New project*" -or $_.Path -like "*.venv\\Scripts\\python.exe"
    } |
    Stop-Process -Force -ErrorAction SilentlyContinue

$launchCommand = 'start "HBX Server" powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "{0}"' -f $serverScript
cmd /c $launchCommand | Out-Null
Start-Sleep -Seconds 8

$listener = netstat -ano | Select-String ":8000"
if (-not $listener) {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Error "A janela do servidor foi aberta, mas a porta 8000 nao respondeu. Verifique a janela do servidor."
    exit 1
}

$serverPid = ($listener | Select-Object -First 1).ToString().Trim() -split '\s+' | Select-Object -Last 1
$serverPid | Out-File -FilePath $pidFile -Encoding ascii -Force
Write-Host "Servidor HBX iniciado com sucesso (PID $serverPid)."
Write-Host "Acesse: http://127.0.0.1:8000"
