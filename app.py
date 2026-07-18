from flask import Flask, render_template, request, redirect, session
from database import conectar, criar_banco


app = Flask(__name__)

app.secret_key = "pastelcontrol123"


criar_banco()



# ==========================
# LOGIN
# ==========================

@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":

        nome = request.form["nome"]

        senha = request.form["senha"]


        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT *

                       FROM usuarios

                       WHERE nome=%s AND senha=%s

                       """,
                       (
                           nome,
                           senha
                       ))


        usuario = cursor.fetchone()


        conn.close()


        if usuario:

            session["usuario"] = usuario[1]

            session["nivel"] = usuario[3]


            return redirect("/dashboard")



    return render_template("login.html")





# ==========================
# DASHBOARD
# ==========================

@app.route("/dashboard")
def dashboard():

    if "usuario" not in session:

        return redirect("/")


    conn = conectar()

    cursor = conn.cursor()


    # Busca o último caixa
    cursor.execute("""
    SELECT
        id,
        data,
        usuario,
        caixa_inicial,
        caixa_final,
        maquina1,
        maquina2,
        maquina3,
        maquina4,
        dinheiro,
        pix,
        status

    FROM controle

    ORDER BY id DESC

    LIMIT 1

    """)


    ultimo = cursor.fetchone()



    # Verifica se existe caixa aberto
    cursor.execute("""
    SELECT COUNT(*)

    FROM controle

    WHERE UPPER(status)='ABERTO'

    """)


    caixa_aberto = cursor.fetchone()[0] > 0



    conn.close()



    return render_template(

        "dashboard.html",

        usuario=session["usuario"],

        ultimo=ultimo,

        caixa_aberto=caixa_aberto

    )
# ==========================
# ABERTURA DO CAIXA
# ==========================


@app.route("/abertura", methods=["GET","POST"])
def abertura():

    if "usuario" not in session:

        return redirect("/")



    conn = conectar()

    cursor = conn.cursor()



    cursor.execute("""
    SELECT

    id,

    nome,

    categoria

    FROM produtos

    ORDER BY categoria,nome

    """)


    produtos = cursor.fetchall()





    if request.method == "POST":

        data = request.form["data"]


        caixa = float(
            request.form.get(
                "caixa",
                0
            )
        )

        cursor.execute("""
                       INSERT INTO controle

                       (data,
                        usuario,
                        caixa_inicial,
                        status)

                       VALUES (%s, %s, %s, %s) RETURNING id

                       """,
                       (
                           data,
                           session["usuario"],
                           caixa,
                           "ABERTO"
                       ))

        controle_id = cursor.fetchone()[0]






        for produto in produtos:


            quantidade = int(
                request.form.get(
                    f"produto_{produto[0]}",
                    0
                )
            )


            cursor.execute("""
            INSERT INTO producao

            (
            controle_id,
            produto_id,
            quantidade
            )

            VALUES (%s,%s,%s)

            """,
            (
                controle_id,
                produto[0],
                quantidade
            ))





        conn.commit()

        conn.close()


        return redirect("/dashboard")






    conn.close()



    return render_template(

        "abertura.html",

        produtos=produtos

    )
# ==========================
# FECHAMENTO DO CAIXA
# ==========================

@app.route("/fechamento", methods=["GET","POST"])
def fechamento():

    if "usuario" not in session:

        return redirect("/")



    conn = conectar()

    cursor = conn.cursor()



    cursor.execute("""
    SELECT *

    FROM controle

    WHERE status='ABERTO'

    ORDER BY id DESC

    LIMIT 1

    """)


    controle = cursor.fetchone()



    if controle is None:

        conn.close()

        return redirect("/abertura")





    cursor.execute("""
    SELECT

    producao.id,

    produtos.id,

    produtos.nome,

    produtos.categoria,

    producao.quantidade


    FROM producao


    INNER JOIN produtos

    ON produtos.id = producao.produto_id


    WHERE producao.controle_id=%s


    ORDER BY produtos.categoria, produtos.nome

    """,
    (
        controle[0],
    ))


    produtos = cursor.fetchall()





    if request.method == "POST":



        for produto in produtos:


            sobra = int(
                request.form.get(
                    f"final_{produto[0]}",
                    0
                )
            )


            perda = int(
                request.form.get(
                    f"perda_{produto[0]}",
                    0
                )
            )



            cursor.execute("""
            INSERT INTO estoque

            (
            controle_id,
            produto_id,
            quantidade_final,
            perda
            )

            VALUES (%s,%s,%s,%s)

            """,
            (
                controle[0],
                produto[1],
                sobra,
                perda
            ))







        maquina1 = float(
            request.form.get("maquina1",0)
        )

        maquina2 = float(
            request.form.get("maquina2",0)
        )

        maquina3 = float(
            request.form.get("maquina3",0)
        )

        maquina4 = float(
            request.form.get("maquina4",0)
        )


        dinheiro = float(
            request.form.get("dinheiro",0)
        )


        pix = float(
            request.form.get("pix",0)
        )



        total = (

            maquina1 +
            maquina2 +
            maquina3 +
            maquina4 +
            dinheiro +
            pix

        )

        cursor.execute("""
                       UPDATE controle

                       SET caixa_final=%s,

                           maquina1=%s,

                           maquina2=%s,

                           maquina3=%s,

                           maquina4=%s,

                           dinheiro=%s,

                           pix=%s,

                           status=%s


                       WHERE id = %s

                       """,
                       (
                           total,

                           maquina1,

                           maquina2,

                           maquina3,

                           maquina4,

                           dinheiro,

                           pix,

                           "FECHADO",

                           controle[0]

                       ))





        conn.commit()
        cursor.execute("""
                       SELECT status
                       FROM controle
                       WHERE id = %s
                       """,
                       (
                           controle[0],
                       ))

        print(
            "STATUS SALVO:",
            cursor.fetchone()
        )

        conn.close()


        return redirect("/dashboard")







    conn.close()


    return render_template(

        "fechamento.html",

        produtos=produtos,

        data=controle[1]

    )








# ==========================
# PRODUTOS
# ==========================


@app.route("/produtos", methods=["GET","POST"])
def produtos():

    if "usuario" not in session:

        return redirect("/")



    if session["nivel"] != "admin":

        return redirect("/dashboard")



    conn = conectar()

    cursor = conn.cursor()





    if request.method == "POST":


        nome = request.form["nome"]

        categoria = request.form["categoria"]



        cursor.execute("""
        INSERT INTO produtos

        (
        nome,
        categoria
        )

        VALUES (%s,%s)

        """,
        (
            nome,
            categoria
        ))



        conn.commit()





    cursor.execute("""
    SELECT *

    FROM produtos

    ORDER BY categoria,nome

    """)


    lista = cursor.fetchall()


    conn.close()



    return render_template(

        "produtos.html",

        produtos=lista

    )








@app.route("/excluir_produto/<int:id>")
def excluir_produto(id):


    if "usuario" not in session:

        return redirect("/")



    if session["nivel"] != "admin":

        return redirect("/dashboard")



    conn = conectar()

    cursor = conn.cursor()



    cursor.execute("""
    DELETE FROM produtos

    WHERE id=%s

    """,
    (
        id,
    ))



    conn.commit()

    conn.close()


    return redirect("/produtos")

# ==========================
# USUÁRIOS
# ==========================

@app.route("/usuarios", methods=["GET","POST"])
def usuarios():


    if "usuario" not in session:

        return redirect("/")



    if session["nivel"] != "admin":

        return redirect("/dashboard")



    conn = conectar()

    cursor = conn.cursor()




    if request.method == "POST":


        nome = request.form["nome"]

        senha = request.form["senha"]

        nivel = request.form["nivel"]





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
            nome,
            senha,
            nivel
        ))



        conn.commit()





    cursor.execute("""
    SELECT *

    FROM usuarios

    ORDER BY nome

    """)


    lista = cursor.fetchall()



    conn.close()



    return render_template(

        "usuarios.html",

        usuarios=lista

    )








@app.route("/excluir_usuario/<int:id>")
def excluir_usuario(id):


    if "usuario" not in session:

        return redirect("/")



    if session["nivel"] != "admin":

        return redirect("/dashboard")



    conn = conectar()

    cursor = conn.cursor()



    cursor.execute("""
    DELETE FROM usuarios

    WHERE id=%s

    """,
    (
        id,
    ))



    conn.commit()

    conn.close()



    return redirect("/usuarios")









# ==========================
# RELATÓRIOS
# ==========================

@app.route("/relatorios")
def relatorios():

    if "usuario" not in session:
        return redirect("/")


    if session["nivel"] != "admin":
        return redirect("/dashboard")


    conn = conectar()

    cursor = conn.cursor()


    data_filtro = request.args.get("data")


    if data_filtro:

        cursor.execute("""
        SELECT *

        FROM controle

        WHERE data=%s

        ORDER BY id DESC

        """,
        (
            data_filtro,
        ))

    else:

        cursor.execute("""
        SELECT *

        FROM controle

        ORDER BY id DESC

        """)


    controles = cursor.fetchall()



    resumo = []



    for controle in controles:


        cursor.execute("""
        SELECT


        produtos.nome,


        produtos.categoria,


        producao.quantidade,


        COALESCE(estoque.quantidade_final,0),


        COALESCE(estoque.perda,0)



        FROM producao



        INNER JOIN produtos


        ON produtos.id = producao.produto_id



        LEFT JOIN estoque


        ON estoque.produto_id = producao.produto_id


        AND estoque.controle_id = producao.controle_id



        WHERE producao.controle_id=%s



        """,
        (
            controle[0],
        ))



        produtos = cursor.fetchall()



        for produto in produtos:


            produzido = produto[2]

            sobra = produto[3]

            perda = produto[4]


            consumo = produzido - sobra - perda


            if consumo < 0:
                consumo = 0



            resumo.append(

                (
                    produto[0],
                    produto[1],
                    consumo,
                    perda,
                    produzido,
                    sobra
                )

            )



    conn.close()


    return render_template(

        "relatorios.html",

        controles=controles,

        resumo=resumo,

        data_filtro=data_filtro

    )
# ==========================
# LOGOUT
# ==========================


@app.route("/logout")
def logout():


    session.clear()


    return redirect("/")









# ==========================
# INICIAR SISTEMA
# ==========================


if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )