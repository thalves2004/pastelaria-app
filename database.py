import sqlite3


BANCO = "pastelaria.db"



def conectar():

    return sqlite3.connect(BANCO)





def criar_banco():

    conn = conectar()

    cursor = conn.cursor()





    # USUÁRIOS

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        nome TEXT NOT NULL,

        senha TEXT NOT NULL,

        nivel TEXT NOT NULL

    )
    """)







    # PRODUTOS

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        nome TEXT NOT NULL,

        categoria TEXT NOT NULL

    )
    """)







    # CONTROLE DO DIA

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS controle(

        id INTEGER PRIMARY KEY AUTOINCREMENT,


        data TEXT NOT NULL,


        usuario TEXT,


        caixa_inicial REAL DEFAULT 0,


        caixa_final REAL DEFAULT 0,


        maquina1 REAL DEFAULT 0,


        maquina2 REAL DEFAULT 0,


        maquina3 REAL DEFAULT 0,


        maquina4 REAL DEFAULT 0,


        dinheiro REAL DEFAULT 0,


        pix REAL DEFAULT 0,


        status TEXT DEFAULT 'ABERTO'

    )
    """)








    # PRODUÇÃO DO DIA

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS producao(

        id INTEGER PRIMARY KEY AUTOINCREMENT,


        controle_id INTEGER,


        produto_id INTEGER,


        quantidade INTEGER DEFAULT 0

    )
    """)








    # ESTOQUE / FECHAMENTO

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estoque(

        id INTEGER PRIMARY KEY AUTOINCREMENT,


        controle_id INTEGER,


        produto_id INTEGER,


        quantidade_final INTEGER DEFAULT 0,


        perda INTEGER DEFAULT 0

    )
    """)









    # ADMIN PADRÃO


    cursor.execute("""
    SELECT *

    FROM usuarios

    WHERE nome='admin'
    """)



    admin = cursor.fetchone()



    if admin is None:


        cursor.execute("""
        INSERT INTO usuarios

        (nome, senha, nivel)

        VALUES (?,?,?)

        """,
        (
            "admin",
            "123",
            "admin"
        ))






    conn.commit()

    conn.close()