from decimal import Decimal, InvalidOperation
from flask import Flask, render_template, request, redirect, session
from database import conectar, criar_banco

app = Flask(__name__)
app.secret_key = "pastelcontrol123"
criar_banco()


def numero(nome):
    valor = (request.form.get(nome) or "0").replace(",", ".")
    try:
        return Decimal(valor)
    except InvalidOperation:
        return Decimal("0")


def inteiro(nome):
    try:
        return max(0, int(request.form.get(nome, 0) or 0))
    except (TypeError, ValueError):
        return 0


def autenticado():
    return "usuario" in session


def admin():
    return session.get("nivel") == "admin"


@app.route("/", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        conn = conectar(); cursor = conn.cursor()
        cursor.execute("SELECT id,nome,senha,nivel FROM usuarios WHERE nome=%s AND senha=%s",
                       (request.form.get("nome"), request.form.get("senha")))
        usuario = cursor.fetchone(); cursor.close(); conn.close()
        if usuario:
            session["usuario"] = usuario[1]
            session["nivel"] = usuario[3]
            return redirect("/dashboard")
        erro = "Usuário ou senha inválidos."
    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    if not autenticado(): return redirect("/")
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("""
        SELECT id,data,usuario,caixa_inicial,caixa_final,maquina1,maquina2,
               maquina3,maquina4,dinheiro,pix,status
        FROM controle ORDER BY id DESC LIMIT 1
    """)
    ultimo = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM controle WHERE UPPER(status)='ABERTO'")
    caixa_aberto = cursor.fetchone()[0] > 0
    cursor.close(); conn.close()
    return render_template("dashboard.html", usuario=session["usuario"], ultimo=ultimo,
                           caixa_aberto=caixa_aberto)


@app.route("/abertura", methods=["GET", "POST"])
def abertura():
    if not autenticado(): return redirect("/")
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("SELECT id,nome,categoria FROM produtos ORDER BY categoria,nome")
    produtos = cursor.fetchall()
    if request.method == "POST":
        cursor.execute("SELECT COUNT(*) FROM controle WHERE UPPER(status)='ABERTO'")
        if cursor.fetchone()[0] > 0:
            cursor.close(); conn.close(); return redirect("/fechamento")
        cursor.execute("""
            INSERT INTO controle (data,usuario,caixa_inicial,status)
            VALUES (%s,%s,%s,'ABERTO') RETURNING id
        """, (request.form.get("data"), session["usuario"], numero("caixa")))
        controle_id = cursor.fetchone()[0]
        for produto in produtos:
            cursor.execute("INSERT INTO producao (controle_id,produto_id,quantidade) VALUES (%s,%s,%s)",
                           (controle_id, produto[0], inteiro(f"produto_{produto[0]}")))
        conn.commit(); cursor.close(); conn.close()
        return redirect("/dashboard")
    cursor.close(); conn.close()
    return render_template("abertura.html", produtos=produtos,
                           pasteis=[p for p in produtos if p[2].lower() == "pastel"],
                           bebidas=[p for p in produtos if p[2].lower() == "bebida"])


@app.route("/fechamento", methods=["GET", "POST"])
def fechamento():
    if not autenticado(): return redirect("/")
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("SELECT id,data,caixa_inicial FROM controle WHERE UPPER(status)='ABERTO' ORDER BY id DESC LIMIT 1")
    controle = cursor.fetchone()
    if not controle:
        cursor.close(); conn.close(); return redirect("/abertura")

    cursor.execute("""
        SELECT pr.id,p.id,p.nome,p.categoria,pr.quantidade
        FROM producao pr JOIN produtos p ON p.id=pr.produto_id
        WHERE pr.controle_id=%s ORDER BY p.categoria,p.nome
    """, (controle[0],))
    produtos = cursor.fetchall()

    if request.method == "POST":
        total_sobra_pasteis = 0
        total_consumo_pasteis = 0
        for producao_id, produto_id, nome, categoria, produzido in produtos:
            sobra = inteiro(f"final_{producao_id}")
            perda = inteiro(f"perda_{producao_id}")
            brinde = inteiro(f"brinde_{producao_id}")
            consumo = inteiro(f"consumo_{producao_id}")
            sobra_frita = inteiro(f"sobra_frita_{producao_id}")
            vendido = max(0, produzido - sobra - perda - brinde - consumo - sobra_frita)
            if categoria.lower() == "pastel":
                total_sobra_pasteis += sobra + sobra_frita
                total_consumo_pasteis += consumo
            cursor.execute("DELETE FROM estoque WHERE controle_id=%s AND produto_id=%s", (controle[0], produto_id))
            cursor.execute("""
                INSERT INTO estoque
                (controle_id,produto_id,quantidade_final,perda,brinde,consumo,sobra_frita)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (controle[0], produto_id, sobra, perda, brinde, consumo, sobra_frita))

        m1, m2, m3, m4 = [numero(f"maquina{i}") for i in range(1,5)]
        pix = numero("pix")
        troco_total = numero("troco_total")
        dinheiro_50 = numero("dinheiro_50")
        dinheiro_100 = numero("dinheiro_100")
        dinheiro_200 = numero("dinheiro_200")
        dinheiro = troco_total + dinheiro_50 + dinheiro_100 + dinheiro_200
        descontos = numero("descontos")
        fornecedores = numero("fornecedores")
        seguranca = numero("seguranca")
        outras = numero("outras_despesas")
        total_bruto = m1 + m2 + m3 + m4 + dinheiro + pix
        total_liquido = total_bruto - descontos - fornecedores - seguranca - outras

        cursor.execute("""
            UPDATE controle SET caixa_final=%s,maquina1=%s,maquina2=%s,maquina3=%s,
                maquina4=%s,dinheiro=%s,pix=%s,troco_total=%s,dinheiro_50=%s,
                dinheiro_100=%s,dinheiro_200=%s,sobra_pasteis=%s,consumo_pasteis=%s,
                descontos=%s,fornecedores=%s,seguranca=%s,outras_despesas=%s,
                status='FECHADO' WHERE id=%s
        """, (total_liquido,m1,m2,m3,m4,dinheiro,pix,troco_total,dinheiro_50,
              dinheiro_100,dinheiro_200,total_sobra_pasteis,total_consumo_pasteis,
              descontos,fornecedores,seguranca,outras,controle[0]))
        conn.commit(); cursor.close(); conn.close()
        return redirect("/dashboard")

    cursor.close(); conn.close()
    return render_template("fechamento.html", produtos=produtos, data=controle[1],
                           caixa_inicial=controle[2])


@app.route("/produtos")
def produtos():
    # Os produtos são fixos nesta versão; a tela de cadastro foi removida.
    if not autenticado():
        return redirect("/")
    return redirect("/dashboard")


@app.route("/excluir_produto/<int:id>")
def excluir_produto(id):
    return redirect("/dashboard")


@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    if not autenticado(): return redirect("/")
    if not admin(): return redirect("/dashboard")
    conn = conectar(); cursor = conn.cursor()
    if request.method == "POST":
        cursor.execute("""
            INSERT INTO usuarios (nome,senha,nivel)
            SELECT %s,%s,%s
            WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE nome=%s)
        """, (request.form.get("nome"), request.form.get("senha"),
              request.form.get("nivel"), request.form.get("nome")))
        conn.commit()
    cursor.execute("SELECT * FROM usuarios ORDER BY nome")
    lista = cursor.fetchall(); cursor.close(); conn.close()
    return render_template("usuarios.html", usuarios=lista)


@app.route("/excluir_usuario/<int:id>")
def excluir_usuario(id):
    if not autenticado() or not admin(): return redirect("/dashboard")
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id=%s", (id,)); conn.commit()
    cursor.close(); conn.close(); return redirect("/usuarios")


@app.route("/relatorios")
def relatorios():
    if not autenticado(): return redirect("/")
    if not admin(): return redirect("/dashboard")
    conn = conectar(); cursor = conn.cursor()
    data_filtro = request.args.get("data")
    sql = """
        SELECT id,data,usuario,caixa_inicial,caixa_final,maquina1,maquina2,maquina3,
        maquina4,dinheiro,pix,status,troco_50,troco_20,troco_10,troco_5,troco_2,
        moedas,dinheiro_grande,sobra_pasteis,consumo_pasteis,descontos,fornecedores,
        seguranca,outras_despesas,troco_total,dinheiro_50,dinheiro_100,dinheiro_200 FROM controle
    """
    if data_filtro:
        cursor.execute(sql + " WHERE data=%s ORDER BY id DESC", (data_filtro,))
    else:
        cursor.execute(sql + " ORDER BY id DESC")
    controles = cursor.fetchall()
    relatorios = []
    for controle in controles:
        cursor.execute("""
            SELECT p.nome,p.categoria,pr.quantidade,
                   COALESCE(e.quantidade_final,0),COALESCE(e.perda,0),
                   COALESCE(e.brinde,0),COALESCE(e.consumo,0),COALESCE(e.sobra_frita,0)
            FROM producao pr JOIN produtos p ON p.id=pr.produto_id
            LEFT JOIN estoque e ON e.controle_id=pr.controle_id AND e.produto_id=pr.produto_id
            WHERE pr.controle_id=%s ORDER BY p.categoria,p.nome
        """, (controle[0],))
        itens = cursor.fetchall()
        relatorios.append((controle,itens))
    cursor.close(); conn.close()
    return render_template("relatorios.html", relatorios=relatorios, data_filtro=data_filtro)


@app.route("/editar_relatorio/<int:id>", methods=["GET", "POST"])
def editar_relatorio(id):
    if not autenticado() or not admin():
        return redirect("/dashboard")
    conn = conectar(); cursor = conn.cursor()
    if request.method == "POST":
        m1, m2, m3, m4 = [numero(f"maquina{i}") for i in range(1, 5)]
        pix = numero("pix")
        troco_total = numero("troco_total")
        dinheiro_50 = numero("dinheiro_50")
        dinheiro_100 = numero("dinheiro_100")
        dinheiro_200 = numero("dinheiro_200")
        dinheiro = troco_total + dinheiro_50 + dinheiro_100 + dinheiro_200
        descontos = numero("descontos")
        fornecedores = numero("fornecedores")
        seguranca = numero("seguranca")
        outras = numero("outras_despesas")
        caixa_final = m1 + m2 + m3 + m4 + pix + dinheiro - descontos - fornecedores - seguranca - outras
        cursor.execute("""
            UPDATE controle SET caixa_final=%s,maquina1=%s,maquina2=%s,maquina3=%s,
                maquina4=%s,dinheiro=%s,pix=%s,troco_total=%s,dinheiro_50=%s,
                dinheiro_100=%s,dinheiro_200=%s,descontos=%s,fornecedores=%s,
                seguranca=%s,outras_despesas=%s WHERE id=%s
        """, (caixa_final,m1,m2,m3,m4,dinheiro,pix,troco_total,dinheiro_50,
              dinheiro_100,dinheiro_200,descontos,fornecedores,seguranca,outras,id))
        conn.commit(); cursor.close(); conn.close()
        return redirect("/relatorios")
    cursor.execute("""
        SELECT id,data,usuario,caixa_inicial,caixa_final,maquina1,maquina2,maquina3,maquina4,
        dinheiro,pix,status,descontos,fornecedores,seguranca,outras_despesas,
        troco_total,dinheiro_50,dinheiro_100,dinheiro_200 FROM controle WHERE id=%s
    """, (id,))
    controle = cursor.fetchone(); cursor.close(); conn.close()
    return render_template("editar_relatorio.html", controle=controle)


@app.route("/excluir_relatorio/<int:id>")
def excluir_relatorio(id):
    if not autenticado() or not admin(): return redirect("/dashboard")
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("DELETE FROM estoque WHERE controle_id=%s", (id,))
    cursor.execute("DELETE FROM producao WHERE controle_id=%s", (id,))
    cursor.execute("DELETE FROM controle WHERE id=%s", (id,))
    conn.commit(); cursor.close(); conn.close()
    return redirect("/relatorios")


if __name__ == "__main__":
    app.run(debug=True)
