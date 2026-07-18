import psycopg2
import os


def conectar():

    DATABASE_URL = os.environ.get("DATABASE_URL")

    return psycopg2.connect(
        DATABASE_URL
    )


def criar_banco():

    conn = conectar()
    cursor = conn.cursor()


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(

        id SERIAL PRIMARY KEY,

        nome VARCHAR(100),

        senha VARCHAR(100),

        nivel VARCHAR(20)

    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos(

        id SERIAL PRIMARY KEY,

        nome VARCHAR(100),

        categoria VARCHAR(50)

    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS controle(

        id SERIAL PRIMARY KEY,

        data DATE,

        usuario VARCHAR(100),

        caixa_inicial FLOAT,

        caixa_final FLOAT,

        maquina1 FLOAT,

        maquina2 FLOAT,

        maquina3 FLOAT,

        maquina4 FLOAT,

        dinheiro FLOAT,

        pix FLOAT,

        status VARCHAR(20)

    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS producao(

        id SERIAL PRIMARY KEY,

        controle_id INTEGER,

        produto_id INTEGER,

        quantidade INTEGER

    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estoque(

        id SERIAL PRIMARY KEY,

        controle_id INTEGER,

        produto_id INTEGER,

        quantidade_final INTEGER,

        perda INTEGER

    )
    """)


    conn.commit()
    conn.close()