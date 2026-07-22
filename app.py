from decimal import Decimal, InvalidOperation
import json
from flask import Flask, render_template, request, redirect, session
from database import conectar, criar_banco, ORDEM_PRODUTOS

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


def ler_equipe_formulario():
    nomes = request.form.getlist("funcionario_nome[]")
    valores = request.form.getlist("funcionario_diaria[]")
    equipe = []
    for nome, valor in zip(nomes, valores):
        nome = (nome or "").strip()
        if not nome:
            continue
        try:
            diaria = float(str(valor or "0").replace(",", "."))
        except (TypeError, ValueError):
            diaria = 0.0
        equipe.append({"nome": nome, "diaria": max(0, diaria)})
    return equipe



def ler_despesas_formulario():
    nomes = request.form.getlist("despesa_nome[]")
    valores = request.form.getlist("despesa_valor[]")
    despesas = []
    for nome, valor in zip(nomes, valores):
        nome = (nome or "").strip()
        if not nome:
            continue
        try:
            quantia = float(str(valor or "0").replace(",", "."))
        except (TypeError, ValueError):
            quantia = 0.0
        despesas.append({"nome": nome, "valor": max(0, quantia)})
    return despesas


def decodificar_despesas(texto, fornecedores=0, seguranca=0, outras=0):
    try:
        dados = json.loads(texto or "[]")
        if isinstance(dados, list):
            despesas = [
                {"nome": str(item.get("nome", "")).strip(), "valor": float(item.get("valor", 0) or 0)}
                for item in dados if isinstance(item, dict) and str(item.get("nome", "")).strip()
            ]
            if despesas:
                return despesas
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    antigas = []
    for nome, valor in (("Fornecedores", fornecedores), ("Segurança", seguranca), ("Outras despesas", outras)):
        if float(valor or 0) > 0:
            antigas.append({"nome": nome, "valor": float(valor or 0)})
    return antigas


def decodificar_equipe(texto, nomes_antigos=""):
    try:
        dados = json.loads(texto or "[]")
        if isinstance(dados, list):
            equipe = [
                {"nome": str(item.get("nome", "")).strip(), "diaria": float(item.get("diaria", 0) or 0)}
                for item in dados if isinstance(item, dict) and str(item.get("nome", "")).strip()
            ]
            if equipe:
                return equipe
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return [{"nome": n.strip(), "diaria": 0} for n in str(nomes_antigos or "").split(",") if n.strip()]


def ordenar_produtos(lista, indice_nome):
    return sorted(lista, key=lambda item: ORDEM_PRODUTOS.get(str(item[indice_nome]).lower(), 9999))


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


@app.route("/quantidades-padrao", methods=["GET", "POST"])
def quantidades_padrao():
    if not autenticado() or not admin():
        return redirect("/dashboard")

    dias_validos = ["terca", "sabado", "domingo"]
    dia = (request.values.get("dia") or "terca").lower()
    if dia not in dias_validos:
        dia = "terca"

    conn = conectar(); cursor = conn.cursor()
    cursor.execute("SELECT id,nome,categoria FROM produtos ORDER BY categoria,nome")
    produtos = ordenar_produtos(cursor.fetchall(), 1)

    if request.method == "POST":
        for produto in produtos:
            quantidade = inteiro(f"produto_{produto[0]}")
            cursor.execute("""
                INSERT INTO quantidades_padrao (dia_semana, produto_id, quantidade)
                VALUES (%s,%s,%s)
                ON CONFLICT (dia_semana, produto_id)
                DO UPDATE SET quantidade=EXCLUDED.quantidade
            """, (dia, produto[0], quantidade))
        conn.commit()
        cursor.close(); conn.close()
        return redirect(f"/quantidades-padrao?dia={dia}&salvo=1")

    cursor.execute("SELECT produto_id,quantidade FROM quantidades_padrao WHERE dia_semana=%s", (dia,))
    quantidades = {produto_id: quantidade for produto_id, quantidade in cursor.fetchall()}
    cursor.close(); conn.close()
    return render_template("quantidades_padrao.html", dia=dia, quantidades=quantidades,
                           pasteis=[p for p in produtos if p[2].lower() == "pastel"],
                           bebidas=[p for p in produtos if p[2].lower() == "bebida"])


@app.route("/abertura", methods=["GET", "POST"])
def abertura():
    if not autenticado(): return redirect("/")
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("SELECT id,nome,categoria,COALESCE(valor,0) FROM produtos ORDER BY categoria,nome")
    produtos = ordenar_produtos(cursor.fetchall(), 1)
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
            cursor.execute("INSERT INTO producao (controle_id,produto_id,quantidade,valor_unitario) VALUES (%s,%s,%s,%s)",
                           (controle_id, produto[0], inteiro(f"produto_{produto[0]}"), produto[3] or 0))
        conn.commit(); cursor.close(); conn.close()
        return redirect("/dashboard")
    cursor.execute("SELECT dia_semana,produto_id,quantidade FROM quantidades_padrao")
    padroes = {"terca": {}, "sabado": {}, "domingo": {}}
    for dia_semana, produto_id, quantidade in cursor.fetchall():
        if dia_semana in padroes:
            padroes[dia_semana][str(produto_id)] = quantidade or 0
    cursor.close(); conn.close()
    return render_template("abertura.html", produtos=produtos, padroes=padroes,
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
        SELECT pr.id,p.id,p.nome,p.categoria,pr.quantidade,COALESCE(NULLIF(pr.valor_unitario,0),p.valor,0)
        FROM producao pr JOIN produtos p ON p.id=pr.produto_id
        WHERE pr.controle_id=%s ORDER BY p.categoria,p.nome
    """, (controle[0],))
    produtos = ordenar_produtos(cursor.fetchall(), 2)
    pasteis = [p for p in produtos if p[3].lower() == "pastel"]
    bebidas = [p for p in produtos if p[3].lower() == "bebida"]

    if request.method == "POST":
        total_sobra_pasteis = 0
        total_consumo_pasteis = 0
        for producao_id, produto_id, nome, categoria, produzido, valor_unitario in produtos:
            sobra = inteiro(f"final_{producao_id}")
            perda = inteiro(f"perda_{producao_id}")
            if categoria.lower() == "bebida":
                brinde = 0
                consumo = inteiro(f"consumo_{producao_id}")
                sobra_frita = 0
            else:
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
        dinheiro_grande = numero("dinheiro_grande")
        dinheiro = troco_total + dinheiro_grande
        descontos = numero("descontos")
        despesas = ler_despesas_formulario()
        despesas_durante_total = sum(Decimal(str(item["valor"])) for item in despesas)
        despesas_detalhes = json.dumps(despesas, ensure_ascii=False)
        equipe = ler_equipe_formulario()
        equipe_dia = ", ".join(pessoa["nome"] for pessoa in equipe)
        equipe_detalhes = json.dumps(equipe, ensure_ascii=False)
        diarias_total = sum(Decimal(str(pessoa["diaria"])) for pessoa in equipe)
        total_apurado = m1 + m2 + m3 + m4 + dinheiro + pix
        # Despesas pagas durante a feira já saíram do caixa e não podem ser descontadas novamente.
        # Somente as diárias são pagas depois do fechamento.
        total_liquido = total_apurado - diarias_total

        cursor.execute("""
            UPDATE controle SET caixa_final=%s,maquina1=%s,maquina2=%s,maquina3=%s,
                maquina4=%s,dinheiro=%s,pix=%s,troco_total=%s,dinheiro_grande=%s,
                dinheiro_50=0,dinheiro_100=0,dinheiro_200=0,
                sobra_pasteis=%s,consumo_pasteis=%s,
                descontos=%s,fornecedores=0,seguranca=0,outras_despesas=0,
                despesas_detalhes=%s,despesas_durante_total=%s,
                equipe_dia=%s,equipe_detalhes=%s,diarias_total=%s,
                status='FECHADO' WHERE id=%s
        """, (total_liquido,m1,m2,m3,m4,dinheiro,pix,troco_total,dinheiro_grande,
              total_sobra_pasteis,total_consumo_pasteis,
              descontos,despesas_detalhes,despesas_durante_total,equipe_dia,equipe_detalhes,
              diarias_total,controle[0]))
        conn.commit(); cursor.close(); conn.close()
        return redirect("/dashboard")

    cursor.close(); conn.close()
    return render_template("fechamento.html", produtos=produtos, pasteis=pasteis, bebidas=bebidas,
                           data=controle[1], caixa_inicial=controle[2])


@app.route("/valores", methods=["GET", "POST"])
def valores_produtos():
    if not autenticado():
        return redirect("/")
    if not admin():
        return redirect("/dashboard")
    conn = conectar(); cursor = conn.cursor()
    if request.method == "POST":
        cursor.execute("SELECT id FROM produtos")
        for (produto_id,) in cursor.fetchall():
            novo_valor = numero(f"valor_{produto_id}")
            cursor.execute("UPDATE produtos SET valor=%s WHERE id=%s", (novo_valor, produto_id))
            # Se o caixa já estiver aberto, aplica o novo valor também ao fechamento atual.
            cursor.execute("""
                UPDATE producao SET valor_unitario=%s
                WHERE produto_id=%s AND controle_id IN
                      (SELECT id FROM controle WHERE UPPER(status)='ABERTO')
            """, (novo_valor, produto_id))
        conn.commit()
        cursor.close(); conn.close()
        return redirect("/valores?salvo=1")
    cursor.execute("SELECT id,nome,categoria,COALESCE(valor,0) FROM produtos ORDER BY categoria,nome")
    produtos = ordenar_produtos(cursor.fetchall(), 1)
    cursor.close(); conn.close()
    return render_template("valores.html",
                           pasteis=[p for p in produtos if p[2].lower() == "pastel"],
                           bebidas=[p for p in produtos if p[2].lower() == "bebida"],
                           salvo=request.args.get("salvo"))


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
        seguranca,outras_despesas,troco_total,dinheiro_50,dinheiro_100,dinheiro_200,
        equipe_dia,equipe_detalhes,diarias_total,despesas_detalhes,despesas_durante_total FROM controle
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
                   COALESCE(e.brinde,0),COALESCE(e.consumo,0),COALESCE(e.sobra_frita,0),
                   COALESCE(NULLIF(pr.valor_unitario,0),p.valor,0)
            FROM producao pr JOIN produtos p ON p.id=pr.produto_id
            LEFT JOIN estoque e ON e.controle_id=pr.controle_id AND e.produto_id=pr.produto_id
            WHERE pr.controle_id=%s ORDER BY p.categoria,p.nome
        """, (controle[0],))
        itens = ordenar_produtos(cursor.fetchall(), 0)
        equipe = decodificar_equipe(controle[30] if len(controle) > 30 else "", controle[29] if len(controle) > 29 else "")
        despesas = decodificar_despesas(
            controle[32] if len(controle) > 32 else "",
            controle[22] if len(controle) > 22 else 0,
            controle[23] if len(controle) > 23 else 0,
            controle[24] if len(controle) > 24 else 0,
        )
        relatorios.append((controle,itens,equipe,despesas))
    cursor.close(); conn.close()
    return render_template("relatorios.html", relatorios=relatorios, data_filtro=data_filtro)


@app.route("/editar_relatorio/<int:id>", methods=["GET", "POST"])
def editar_relatorio(id):
    if not autenticado() or not admin():
        return redirect("/dashboard")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM controle WHERE id=%s", (id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return redirect("/relatorios")

    cursor.execute("""
        SELECT pr.id, p.id, p.nome, p.categoria, pr.quantidade,
               COALESCE(e.quantidade_final, 0), COALESCE(e.perda, 0),
               COALESCE(e.brinde, 0), COALESCE(e.consumo, 0),
               COALESCE(e.sobra_frita, 0), COALESCE(NULLIF(pr.valor_unitario,0),p.valor,0)
        FROM producao pr
        JOIN produtos p ON p.id = pr.produto_id
        LEFT JOIN estoque e
          ON e.controle_id = pr.controle_id AND e.produto_id = pr.produto_id
        WHERE pr.controle_id=%s
        ORDER BY p.categoria, p.nome
    """, (id,))
    itens = ordenar_produtos(cursor.fetchall(), 2)
    pasteis = [item for item in itens if item[3].lower() == "pastel"]
    bebidas = [item for item in itens if item[3].lower() == "bebida"]

    if request.method == "POST":
        total_sobra_pasteis = 0
        total_consumo_pasteis = 0

        for producao_id, produto_id, nome, categoria, quantidade, *_ in itens:
            saida = inteiro(f"saida_{producao_id}")
            retorno = inteiro(f"final_{producao_id}")
            perda = inteiro(f"perda_{producao_id}")
            if categoria.lower() == "bebida":
                brinde = 0
                consumo = inteiro(f"consumo_{producao_id}")
                sobra_frita = 0
            else:
                brinde = inteiro(f"brinde_{producao_id}")
                consumo = inteiro(f"consumo_{producao_id}")
                sobra_frita = inteiro(f"sobra_frita_{producao_id}")

            cursor.execute(
                "UPDATE producao SET quantidade=%s WHERE id=%s AND controle_id=%s",
                (saida, producao_id, id),
            )
            cursor.execute(
                "DELETE FROM estoque WHERE controle_id=%s AND produto_id=%s",
                (id, produto_id),
            )
            cursor.execute("""
                INSERT INTO estoque
                    (controle_id, produto_id, quantidade_final, perda, brinde, consumo, sobra_frita)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (id, produto_id, retorno, perda, brinde, consumo, sobra_frita))

            if categoria.lower() == "pastel":
                total_sobra_pasteis += retorno + sobra_frita
                total_consumo_pasteis += consumo

        m1, m2, m3, m4 = [numero(f"maquina{i}") for i in range(1, 5)]
        pix = numero("pix")
        troco_total = numero("troco_total")
        dinheiro_grande = numero("dinheiro_grande")
        dinheiro = troco_total + dinheiro_grande
        descontos = numero("descontos")
        despesas = ler_despesas_formulario()
        despesas_durante_total = sum(Decimal(str(item["valor"])) for item in despesas)
        despesas_detalhes = json.dumps(despesas, ensure_ascii=False)
        equipe = ler_equipe_formulario()
        equipe_dia = ", ".join(pessoa["nome"] for pessoa in equipe)
        equipe_detalhes = json.dumps(equipe, ensure_ascii=False)
        diarias_total = sum(Decimal(str(pessoa["diaria"])) for pessoa in equipe)
        total_apurado = m1 + m2 + m3 + m4 + pix + dinheiro
        caixa_final = total_apurado - diarias_total

        cursor.execute("""
            UPDATE controle SET
                caixa_final=%s, maquina1=%s, maquina2=%s, maquina3=%s,
                maquina4=%s, dinheiro=%s, pix=%s, troco_total=%s,
                dinheiro_grande=%s, dinheiro_50=0, dinheiro_100=0, dinheiro_200=0,
                sobra_pasteis=%s, consumo_pasteis=%s, descontos=%s,
                fornecedores=0, seguranca=0, outras_despesas=0,
                despesas_detalhes=%s, despesas_durante_total=%s, equipe_dia=%s,
                equipe_detalhes=%s, diarias_total=%s
            WHERE id=%s
        """, (
            caixa_final, m1, m2, m3, m4, dinheiro, pix, troco_total,
            dinheiro_grande, total_sobra_pasteis, total_consumo_pasteis,
            descontos, despesas_detalhes, despesas_durante_total, equipe_dia,
            equipe_detalhes, diarias_total, id,
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect("/relatorios")

    cursor.execute("""
        SELECT id, data, usuario, caixa_inicial, caixa_final,
               maquina1, maquina2, maquina3, maquina4, dinheiro, pix, status,
               descontos, fornecedores, seguranca, outras_despesas,
               troco_total,
               COALESCE(NULLIF(dinheiro_grande, 0),
                        COALESCE(dinheiro_50, 0) + COALESCE(dinheiro_100, 0) + COALESCE(dinheiro_200, 0)),
               COALESCE(equipe_dia, ''), COALESCE(equipe_detalhes, '[]'),
               COALESCE(diarias_total, 0), COALESCE(despesas_detalhes, '[]'),
               COALESCE(despesas_durante_total, 0)
        FROM controle WHERE id=%s
    """, (id,))
    controle = cursor.fetchone()
    equipe = decodificar_equipe(controle[19] if len(controle) > 19 else "", controle[18] if len(controle) > 18 else "")
    despesas = decodificar_despesas(
        controle[21] if len(controle) > 21 else "",
        controle[13] if len(controle) > 13 else 0,
        controle[14] if len(controle) > 14 else 0,
        controle[15] if len(controle) > 15 else 0,
    )
    cursor.close()
    conn.close()
    return render_template("editar_relatorio.html", controle=controle, itens=itens, pasteis=pasteis, bebidas=bebidas, equipe=equipe, despesas=despesas)


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
