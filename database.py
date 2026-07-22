import os
import psycopg2
import re
import unicodedata


def conectar():
    """Retorna uma conexão PostgreSQL usando DATABASE_URL."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("A variável DATABASE_URL não foi configurada.")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(database_url)


get_connection = conectar


PRODUTOS_PADRAO = [
    ("Carne", "pastel"), ("Queijo", "pastel"),
    ("Presunto e Queijo", "pastel"), ("Frango e Queijo", "pastel"),
    ("Carne e Queijo", "pastel"), ("Palmito", "pastel"),
    ("Palmito e Queijo", "pastel"), ("Palmito e Frango", "pastel"),
    ("Pastelão", "pastel"), ("Pastelão de Frango", "pastel"),
    ("Enroladão", "pastel"), ("Coxinha de Carne", "pastel"),
    ("Coxinha de Frango", "pastel"),
    ("Massa de 600 gramas", "pastel"),
    ("Coca Normal", "bebida"), ("Coca Zero", "bebida"),
    ("Sprite", "bebida"), ("Guaraná", "bebida"),
    ("Fanta", "bebida"), ("Água", "bebida"),
    ("Suco", "bebida"), ("Chocomilk", "bebida"),
]

ORDEM_PRODUTOS = {nome.lower(): indice for indice, (nome, _) in enumerate(PRODUTOS_PADRAO)}


def normalizar_nome_produto(nome):
    texto = unicodedata.normalize("NFKD", str(nome or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    chave = re.sub(r"\s+", " ", texto).strip().lower()
    # "Pastelão de carne" e "Pastelão" representam o mesmo produto.
    aliases = {
        "pastelao de carne": "pastelao",
        "pastelao carne": "pastelao",
    }
    return aliases.get(chave, chave)


def consolidar_produtos_repetidos(cursor):
    """Une produtos repetidos sem perder produções ou relatórios antigos."""
    cursor.execute("SELECT id, nome, categoria FROM produtos ORDER BY id")
    grupos = {}
    for produto_id, nome, categoria in cursor.fetchall():
        grupos.setdefault(normalizar_nome_produto(nome), []).append((produto_id, nome, categoria))

    padrao_por_chave = {normalizar_nome_produto(nome): (nome, categoria) for nome, categoria in PRODUTOS_PADRAO}

    for chave, registros in grupos.items():
        if len(registros) == 1:
            produto_id, nome_atual, categoria_atual = registros[0]
            if chave in padrao_por_chave:
                nome_correto, categoria_correta = padrao_por_chave[chave]
                cursor.execute("UPDATE produtos SET nome=%s, categoria=%s WHERE id=%s",
                               (nome_correto, categoria_correta, produto_id))
            continue

        principal = registros[0]
        principal_id = principal[0]
        if chave in padrao_por_chave:
            nome_correto, categoria_correta = padrao_por_chave[chave]
            cursor.execute("UPDATE produtos SET nome=%s, categoria=%s WHERE id=%s",
                           (nome_correto, categoria_correta, principal_id))

        for duplicado_id, _, _ in registros[1:]:
            # Consolida a produção por dia antes de trocar a referência.
            cursor.execute("SELECT id, controle_id, quantidade FROM producao WHERE produto_id=%s", (duplicado_id,))
            for producao_id, controle_id, quantidade in cursor.fetchall():
                cursor.execute("SELECT id, quantidade FROM producao WHERE controle_id=%s AND produto_id=%s LIMIT 1",
                               (controle_id, principal_id))
                existente = cursor.fetchone()
                if existente:
                    cursor.execute("UPDATE producao SET quantidade=%s WHERE id=%s",
                                   ((existente[1] or 0) + (quantidade or 0), existente[0]))
                    cursor.execute("DELETE FROM producao WHERE id=%s", (producao_id,))
                else:
                    cursor.execute("UPDATE producao SET produto_id=%s WHERE id=%s", (principal_id, producao_id))

            # Consolida os dados de fechamento e preserva todos os valores.
            cursor.execute("""
                SELECT id, controle_id, quantidade_final, perda, brinde, consumo, sobra_frita
                FROM estoque WHERE produto_id=%s
            """, (duplicado_id,))
            for estoque_id, controle_id, retorno, perda, brinde, consumo, sobra_frita in cursor.fetchall():
                cursor.execute("""
                    SELECT id, quantidade_final, perda, brinde, consumo, sobra_frita
                    FROM estoque WHERE controle_id=%s AND produto_id=%s LIMIT 1
                """, (controle_id, principal_id))
                existente = cursor.fetchone()
                if existente:
                    cursor.execute("""
                        UPDATE estoque SET quantidade_final=%s, perda=%s, brinde=%s, consumo=%s, sobra_frita=%s
                        WHERE id=%s
                    """, (
                        (existente[1] or 0) + (retorno or 0),
                        (existente[2] or 0) + (perda or 0),
                        (existente[3] or 0) + (brinde or 0),
                        (existente[4] or 0) + (consumo or 0),
                        (existente[5] or 0) + (sobra_frita or 0),
                        existente[0],
                    ))
                    cursor.execute("DELETE FROM estoque WHERE id=%s", (estoque_id,))
                else:
                    cursor.execute("UPDATE estoque SET produto_id=%s WHERE id=%s", (principal_id, estoque_id))

            cursor.execute("DELETE FROM produtos WHERE id=%s", (duplicado_id,))


def criar_banco():
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                senha VARCHAR(255) NOT NULL,
                nivel VARCHAR(20) NOT NULL DEFAULT 'funcionario'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                categoria VARCHAR(50) NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS controle (
                id SERIAL PRIMARY KEY,
                data DATE NOT NULL,
                usuario VARCHAR(100),
                caixa_inicial NUMERIC(12,2) DEFAULT 0,
                caixa_final NUMERIC(12,2) DEFAULT 0,
                maquina1 NUMERIC(12,2) DEFAULT 0,
                maquina2 NUMERIC(12,2) DEFAULT 0,
                maquina3 NUMERIC(12,2) DEFAULT 0,
                maquina4 NUMERIC(12,2) DEFAULT 0,
                dinheiro NUMERIC(12,2) DEFAULT 0,
                pix NUMERIC(12,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'ABERTO'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS producao (
                id SERIAL PRIMARY KEY,
                controle_id INTEGER NOT NULL REFERENCES controle(id) ON DELETE CASCADE,
                produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
                quantidade INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estoque (
                id SERIAL PRIMARY KEY,
                controle_id INTEGER NOT NULL REFERENCES controle(id) ON DELETE CASCADE,
                produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
                quantidade_final INTEGER DEFAULT 0,
                perda INTEGER DEFAULT 0
            )
        """)

        # Valor atual de venda de cada produto. Mantido separado do cadastro fixo.
        cursor.execute("ALTER TABLE produtos ADD COLUMN IF NOT EXISTS valor NUMERIC(12,2) DEFAULT 0")
        # Guarda o valor praticado no dia para que relatórios antigos não mudem quando o preço atual for alterado.
        cursor.execute("ALTER TABLE producao ADD COLUMN IF NOT EXISTS valor_unitario NUMERIC(12,2) DEFAULT 0")

        # Quantidades padrão para os dias em que a feira funciona.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quantidades_padrao (
                id SERIAL PRIMARY KEY,
                dia_semana VARCHAR(20) NOT NULL,
                produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
                quantidade INTEGER NOT NULL DEFAULT 0,
                UNIQUE (dia_semana, produto_id)
            )
        """)

        colunas_controle = {
            # Campos antigos mantidos para não perder relatórios anteriores.
            "troco_50": "NUMERIC(12,2) DEFAULT 0",
            "troco_20": "NUMERIC(12,2) DEFAULT 0",
            "troco_10": "NUMERIC(12,2) DEFAULT 0",
            "troco_5": "NUMERIC(12,2) DEFAULT 0",
            "troco_2": "NUMERIC(12,2) DEFAULT 0",
            "moedas": "NUMERIC(12,2) DEFAULT 0",
            "dinheiro_grande": "NUMERIC(12,2) DEFAULT 0",
            # Novo fechamento simplificado.
            "troco_total": "NUMERIC(12,2) DEFAULT 0",
            "dinheiro_50": "NUMERIC(12,2) DEFAULT 0",
            "dinheiro_100": "NUMERIC(12,2) DEFAULT 0",
            "dinheiro_200": "NUMERIC(12,2) DEFAULT 0",
            "sobra_pasteis": "INTEGER DEFAULT 0",
            "consumo_pasteis": "INTEGER DEFAULT 0",
            "descontos": "NUMERIC(12,2) DEFAULT 0",
            "fornecedores": "NUMERIC(12,2) DEFAULT 0",
            "seguranca": "NUMERIC(12,2) DEFAULT 0",
            "outras_despesas": "NUMERIC(12,2) DEFAULT 0",
            "equipe_dia": "TEXT DEFAULT ''",
            "equipe_detalhes": "TEXT DEFAULT '[]'",
            "diarias_total": "NUMERIC(12,2) DEFAULT 0",
            "despesas_detalhes": "TEXT DEFAULT '[]'",
            "despesas_durante_total": "NUMERIC(12,2) DEFAULT 0",
            "dinheiro_adicionado": "NUMERIC(12,2) DEFAULT 0",
        }
        for nome, tipo in colunas_controle.items():
            cursor.execute(f"ALTER TABLE controle ADD COLUMN IF NOT EXISTS {nome} {tipo}")

        colunas_estoque = {
            "brinde": "INTEGER DEFAULT 0",
            "consumo": "INTEGER DEFAULT 0",
            "sobra_frita": "INTEGER DEFAULT 0",
        }
        for nome, tipo in colunas_estoque.items():
            cursor.execute(f"ALTER TABLE estoque ADD COLUMN IF NOT EXISTS {nome} {tipo}")

        # Funciona também em bancos antigos onde usuarios.nome ainda não é UNIQUE.
        cursor.execute("""
            INSERT INTO usuarios (nome, senha, nivel)
            SELECT 'admin', '123', 'admin'
            WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE nome='admin')
        """)

        # Consolida registros antigos repetidos antes de conferir a lista fixa.
        consolidar_produtos_repetidos(cursor)

        # Os produtos passam a ser fixos. Só adiciona os que ainda não existem.
        for nome, categoria in PRODUTOS_PADRAO:
            cursor.execute("""
                INSERT INTO produtos (nome, categoria)
                SELECT %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM produtos WHERE LOWER(nome)=LOWER(%s)
                )
            """, (nome, categoria, nome))

        # Uma segunda passagem elimina possíveis variações de acentos e espaços.
        consolidar_produtos_repetidos(cursor)

        conn.commit()
        print("Banco de dados verificado e atualizado com sucesso.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    criar_banco()
