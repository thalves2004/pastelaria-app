import psycopg2
import os


def conectar():

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1
        )

    return psycopg2.connect(DATABASE_URL)



def criar_banco():

    conn = conectar()
    cursor = conn.cursor()


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(

        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL UNIQUE,
        senha VARCHAR(100) NOT NULL,
        nivel VARCHAR(20) NOT NULL

    )
    """)



    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos(

        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        categoria VARCHAR(50) NOT NULL

    )
    """)



    cursor.execute("""
    CREATE TABLE IF NOT EXISTS controle(

        id SERIAL PRIMARY KEY,

        data DATE,

        usuario VARCHAR(100),

        caixa_inicial FLOAT DEFAULT 0,

        caixa_final FLOAT DEFAULT 0,

        maquina1 FLOAT DEFAULT 0,

        maquina2 FLOAT DEFAULT 0,

        maquina3 FLOAT DEFAULT 0,

        maquina4 FLOAT DEFAULT 0,

        dinheiro FLOAT DEFAULT 0,

        pix FLOAT DEFAULT 0,

        status VARCHAR(20) DEFAULT 'ABERTO'

    )
    """)



    cursor.execute("""
    CREATE TABLE IF NOT EXISTS producao(

        id SERIAL PRIMARY KEY,

        controle_id INTEGER,

        produto_id INTEGER,

        quantidade INTEGER DEFAULT 0

    )
    """)



    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estoque(

        id SERIAL PRIMARY KEY,

        controle_id INTEGER,

        produto_id INTEGER,

        quantidade_final INTEGER DEFAULT 0,

        perda INTEGER DEFAULT 0

    )
    """)



    # cria admin

    cursor.execute("""
    SELECT id FROM usuarios
    WHERE nome='admin'
    """)


    admin = cursor.fetchone()


    if admin is None:

        cursor.execute("""
        INSERT INTO usuarios
        (
        nome,
        senha,
        nivel
        )

        VALUES (%s,%s,%s)

        """,
        (
            "admin",
            "1234",
            "admin"
        ))



    conn.commit()

    cursor.close()

    conn.close()