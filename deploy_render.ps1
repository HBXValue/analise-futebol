$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

Write-Host ""
Write-Host "HBX | Deploy para Render" -ForegroundColor Cyan
Write-Host ""

$branch = git branch --show-current
if ($branch.Trim() -ne "main") {
    Write-Host "Branch atual: $branch" -ForegroundColor Yellow
    throw "O deploy foi configurado para a branch main. Troque para main antes de continuar."
}

Write-Host "1. Validando projeto..." -ForegroundColor Cyan
python manage.py check
python manage.py test valuation

Write-Host ""
$status = git status --short
if (-not $status) {
    Write-Host "Nao ha alteracoes para publicar." -ForegroundColor Yellow
    exit 0
}

Write-Host "Alteracoes detectadas:" -ForegroundColor Cyan
$status | ForEach-Object { Write-Host "  $_" }

Write-Host ""
$commitMessage = Read-Host "Digite a mensagem do commit"
if ([string]::IsNullOrWhiteSpace($commitMessage)) {
    throw "A mensagem do commit nao pode ficar vazia."
}

Write-Host ""
Write-Host "2. Preparando commit..." -ForegroundColor Cyan
git add .
git commit -m $commitMessage

Write-Host ""
Write-Host "3. Enviando para o GitHub..." -ForegroundColor Cyan
git push origin main

Write-Host ""
Write-Host "Concluido." -ForegroundColor Green
Write-Host "Se o auto-deploy estiver ativo no Render, a publicacao iniciara automaticamente." -ForegroundColor Green
