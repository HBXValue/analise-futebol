# Rede Local

Este projeto pode ser usado por 2 ou 3 PCs na mesma rede com um unico PC servidor.

## 1. Escolher o servidor

Escolha um computador que ficara ligado durante o uso do sistema.

## 2. Instalar dependencias no servidor

No PC servidor:

```powershell
cd "C:\Users\User\Documents\New project"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Instalar e configurar PostgreSQL

Crie um banco e um usuario, por exemplo:

- banco: `hbx`
- usuario: `postgres`
- senha: `SUA_SENHA`

## 4. Configurar variaveis de ambiente no servidor

Exemplo em PowerShell para teste da sessao atual:

```powershell
$env:USE_POSTGRES="1"
$env:POSTGRES_DB="hbx"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="SUA_SENHA"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="5432"
$env:DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost,192.168.1.50"
$env:DJANGO_LOCAL_NETWORK_HOSTS="192.168.1.50"
```

Troque `192.168.1.50` pelo IP do PC servidor.

Se preferir, o projeto agora detecta automaticamente os IPs locais do servidor. Nesse caso, basta definir apenas os hosts extras se quiser forcar algum IP manualmente.

## 5. Migrar o banco

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

## 6. Criar usuario inicial

Se precisar:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

## 7. Subir o sistema para a rede local

```powershell
.\.venv\Scripts\waitress-serve.exe --host 0.0.0.0 --port 8000 config.wsgi:application
```

Ou, de forma mais simples:

```powershell
.\start_lan_server.ps1
```

## 8. Liberar a porta no firewall do Windows

Liberar a porta `8000` no PC servidor.

## 9. Acessar dos outros PCs

Nos outros computadores da mesma rede:

```text
http://192.168.1.50:8000
```

## 10. Validar

No servidor:

```powershell
.\.venv\Scripts\python.exe manage.py check
```

Se quiser descobrir o IP do servidor:

```powershell
ipconfig
```
