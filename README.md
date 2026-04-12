# HB Eleven Valuation System

Sistema web em Django para valuation de jogadores de futebol, com autenticação, input manual, upload CSV, dashboard com Plotly e exportação de relatório em PDF.

## Stack

- Python 3.11+
- Django 5.2
- SQLite
- Plotly.js via CDN

## Principais recursos

- Login e criação de conta com senha protegida por hash
- Workspace individual por usuário para agentes e analistas
- Estrutura de dados separada em `users`, `players`, `performance_metrics`, `market_metrics`, `marketing_metrics` e `behavior_metrics`
- Motor de scoring com normalização 0-100
- Score final com projeção de valor e label de potencial
- Radar chart, curva de evolução, comparação de atletas e ranking percentílico por posição
- Cadastro manual e importação por CSV
- Exportação de relatório em PDF
- Placeholders prontos para integrações futuras com Wyscout, Transfermarkt e Instagram API

## Como rodar

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Rode as migrações:

```bash
python manage.py migrate
```

3. Suba o servidor:

```bash
python manage.py runserver
```

4. Abra:

```text
http://127.0.0.1:8000/
```

## Testes

```bash
python manage.py test valuation
```

## Fluxo de uso

1. Crie uma conta em `/signup/`
2. Faça login
3. Cadastre jogadores manualmente em `Add player`
4. Ou importe em lote em `Upload CSV`
5. Analise score, valor projetado, comparação e percentis no dashboard
6. Exporte o PDF individual de cada atleta
