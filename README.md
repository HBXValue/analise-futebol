# HBX

Plataforma Django para cadastro, analise, inteligencia e valorizacao de atletas.

## Stack

- Python 3.11+
- Django 5.2
- SQLite no ambiente local
- PostgreSQL no deploy
- WhiteNoise para arquivos estaticos
- Gunicorn no Render
- Waitress para execucao local em Windows

## Rodando localmente

1. Instale as dependencias:

```bash
pip install -r requirements.txt
```

2. Rode as migracoes:

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

## Rede local

Para abrir em outros PCs da mesma rede:

```powershell
.\start_lan_server.ps1
```

Depois acesse:

```text
http://IP_DO_SERVIDOR:8000
```

## Deploy no Render

O projeto foi preparado para:

- usar `DATABASE_URL` no banco de producao
- servir estaticos com `WhiteNoise`
- usar `gunicorn config.wsgi:application`
- manter fallback para SQLite local quando `DATABASE_URL` nao existir

### Variaveis de ambiente

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=false`
- `DATABASE_URL`
- `RENDER_EXTERNAL_HOSTNAME` (fornecido pelo Render)

### Configuracao recomendada

O arquivo [render.yaml](/C:/Users/User/Documents/New%20project/render.yaml:1) ja inclui:

- instalacao de dependencias
- `collectstatic`
- `migrate`
- web service com Gunicorn
- banco PostgreSQL gerenciado

### Build command

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
```

### Start command

```bash
gunicorn config.wsgi:application
```

## Migrar dados locais para o Render

O deploy publica o codigo, mas nao copia automaticamente o banco local SQLite para o PostgreSQL do Render.

### 1. Exportar sua base local

```powershell
.\export_hbx_data.ps1
```

Isso gera:

```text
fixtures\hbx_data.json
```

### 2. Pegar a Database URL no Render

No painel do Render:

- abra o banco PostgreSQL do projeto
- copie a `External Database URL`

### 3. Importar para o banco do Render

No PowerShell:

```powershell
$env:DATABASE_URL="COLE_A_EXTERNAL_DATABASE_URL_AQUI"
.\import_hbx_data_to_render.ps1
```

Isso vai:

- rodar `migrate` no banco do Render
- importar paises, divisoes, clubes, atletas e dados relacionados

Observacao:

- o fluxo acima e ideal para um banco do Render ainda vazio ou praticamente vazio
- se o banco do Render ja tiver dados conflitantes, a importacao pode falhar por chave primaria duplicada

## Testes

```bash
python manage.py test valuation
```
