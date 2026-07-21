import os
import psycopg2


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
    ("Coca Normal", "bebida"), ("Coca Zero", "bebida"),
    ("Sprite", "bebida"), ("Guaraná", "bebida"),
    ("Fanta", "bebida"), ("Água", "bebida"),
    ("Suco", "bebida"), ("Chocomilk", "bebida"),
]


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

        # Os produtos passam a ser fixos. Só adiciona os que ainda não existem.
        for nome, categoria in PRODUTOS_PADRAO:
            cursor.execute("""
                INSERT INTO produtos (nome, categoria)
                SELECT %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM produtos WHERE LOWER(nome)=LOWER(%s)
                )
            """, (nome, categoria, nome))

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
