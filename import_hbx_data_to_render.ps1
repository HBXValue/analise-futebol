$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$inputFile = Join-Path $projectRoot "fixtures\hbx_data.json"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python da virtualenv nao encontrado em .venv\\Scripts\\python.exe"
    exit 1
}

if (-not (Test-Path $inputFile)) {
    Write-Error "Arquivo de exportacao nao encontrado em fixtures\\hbx_data.json"
    exit 1
}

if (-not $env:DATABASE_URL) {
    Write-Error "DATABASE_URL nao configurada. Copie a External Database URL do Render e defina antes de rodar este script."
    exit 1
}

Write-Host "Aplicando migracoes no banco do Render..."
& $pythonExe manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha ao aplicar migracoes no banco do Render."
    exit $LASTEXITCODE
}

Write-Host "Importando dados para o banco do Render..."
& $pythonExe manage.py loaddata $inputFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha ao importar os dados para o banco do Render."
    exit $LASTEXITCODE
}

Write-Host "Importacao concluida no banco do Render."
