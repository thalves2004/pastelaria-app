# PastelControl — banco Supabase

Este projeto foi preparado para usar PostgreSQL do Supabase mantendo o aplicativo Flask no Render.

## 1. Criar o projeto no Supabase

1. Entre no Supabase e crie um projeto.
2. Guarde a senha definida para o banco.
3. Aguarde o projeto terminar de ser criado.
4. Clique em **Connect**.
5. Copie a URL de **Session pooler** (porta 5432).
6. Substitua o texto `[YOUR-PASSWORD]` pela senha real do banco.

> Use o **Session pooler**, não a conexão direta. Ele funciona melhor quando o serviço de hospedagem não possui IPv6 disponível.

## 2. Configurar o Render

No serviço web do PastelControl:

1. Abra **Environment**.
2. Altere ou crie `DATABASE_URL` com a URL copiada do Supabase.
3. Crie `SECRET_KEY` com uma chave longa e aleatória.
4. Crie `DATABASE_SSLMODE` com o valor `require`.
5. Salve escolhendo a opção para fazer novo deploy.

Não coloque a senha do Supabase diretamente no GitHub.

## 3. Primeiro acesso

No primeiro deploy, o sistema cria e atualiza automaticamente as tabelas. O usuário inicial continua sendo:

- Usuário: `admin`
- Senha: `123`

Troque essa senha depois do primeiro acesso.

## 4. Verificação

Abra no navegador:

`https://SEU-SITE.onrender.com/health`

Resultado esperado:

```json
{"database":"connected","status":"ok"}
```

## Dados do banco antigo

Trocar a `DATABASE_URL` cria um banco novo e vazio. Os dados do banco antigo não são copiados automaticamente. Para preservar históricos, é necessário exportar o PostgreSQL antigo e importar no Supabase antes de remover o banco anterior.
