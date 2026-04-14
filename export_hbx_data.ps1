$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$fixturesDir = Join-Path $projectRoot "fixtures"
$outputFile = Join-Path $fixturesDir "hbx_data.json"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python da virtualenv nao encontrado em .venv\\Scripts\\python.exe"
    exit 1
}

if (-not (Test-Path $fixturesDir)) {
    New-Item -ItemType Directory -Path $fixturesDir | Out-Null
}

Write-Host "Exportando base local para $outputFile ..."
& $pythonExe manage.py export_hbx_data --output $outputFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha ao exportar os dados."
    exit $LASTEXITCODE
}

Write-Host "Exportacao concluida."
Write-Host "Arquivo gerado: $outputFile"
