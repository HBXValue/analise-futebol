$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$waitressExe = Join-Path $projectRoot ".venv\Scripts\waitress-serve.exe"
$port = if ($env:PORT) { $env:PORT } else { "8000" }

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

$networkIps = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
    Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
    ForEach-Object { $_.IPAddressToString } |
    Where-Object { $_ -ne "127.0.0.1" } |
    Select-Object -Unique

if ($networkIps.Count -eq 0) {
    Write-Warning "Nenhum IP de rede local foi detectado automaticamente."
} else {
    $manualHosts = @()
    if ($env:DJANGO_LOCAL_NETWORK_HOSTS) {
        $manualHosts = @($env:DJANGO_LOCAL_NETWORK_HOSTS -split ",")
    }

    $env:DJANGO_LOCAL_NETWORK_HOSTS = (($networkIps + $manualHosts) |
        Where-Object { $_ } |
        Select-Object -Unique) -join ","
}

Write-Host ""
Write-Host "Servidor disponivel em:"
Write-Host "  http://127.0.0.1:$port"
foreach ($ip in $networkIps) {
    Write-Host "  http://${ip}:$port"
}
Write-Host ""
Write-Host "Mantenha esta janela aberta enquanto outros PCs estiverem usando o sistema."
Write-Host ""

if (Test-Path $waitressExe) {
    & $waitressExe --host 0.0.0.0 --port $port config.wsgi:application
    exit $LASTEXITCODE
}

Write-Warning "waitress-serve.exe nao encontrado. Usando runserver."
& $pythonExe manage.py runserver "0.0.0.0:$port"
exit $LASTEXITCODE
