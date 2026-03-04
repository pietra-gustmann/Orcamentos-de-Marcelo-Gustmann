from flask import Flask, render_template, redirect, request, session, Response, url_for
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import sqlite3 
import io
from reportlab.lib.utils import simpleSplit
from reportlab.lib import colors
from reportlab.lib.colors import Color

minha_cor = Color(0.7, 0.1, 0.2)  

app = Flask(__name__)
app.secret_key = "Trabalhoooooooooooooooooooooo"

def init_db():
    conn = sqlite3.connect("instance/banco_trabalho.db")
    conn.execute("PRAGMA foreign_keys = ON")

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produto (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        imagem BLOB
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orcamento (
        id_orcamento INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT NOT NULL,
        cidade TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS item_orcamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_orcamento INTEGER,
        id_produto TEXT,
        nao_incluso INTEGER DEFAULT 0,
        quantidade INTEGER,
        cor TEXT,
        medida TEXT,
        vidro TEXT,
        unitario REAL,
        local TEXT,
        ordem INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(id_orcamento) REFERENCES orcamento(id_orcamento) ON DELETE CASCADE,
        FOREIGN KEY(id_produto) REFERENCES produto(id) ON UPDATE CASCADE
    );
    """)

    conn.commit()
    conn.close()
    
def fmt_money_br(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

init_db()

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/prod_cadastrados')
def prod_cadastrados():
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM produto")
        produtos = cursor.fetchall()

    return render_template("prod_cadastrados.html", produtos=produtos)

@app.route("/excluir_produto/<id>", methods=["POST"])
def excluir_produto(id):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute("DELETE FROM produto WHERE id = ?", (id,))
        conn.commit()

    return redirect("/prod_cadastrados")

@app.route('/imagem/<id>')
def imagem(id):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute("SELECT imagem FROM produto WHERE id = ?", (id,))
        img = cursor.fetchone()

        if img:
            return Response(img[0], mimetype='image/jpeg')

        return '', 404

@app.route("/cadastro_novo_prod", methods=['GET' , 'POST'])
def cadastro_novo_prod():
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        if request.method == 'POST':
            id = request.form['id']
            nome = request.form['nome']
            
            imagem = request.files['imagem']
            imagem = imagem.read()
            
            cursor.execute("""INSERT INTO produto (id, nome, imagem)
                VALUES (?,?,?) """, (id, nome, imagem))

            conn.commit()

    return render_template("cadastro_novo_prod.html")

@app.route("/editar_prod/<id>")
def editar_prod(id):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # orçamento
        cursor.execute(
            "SELECT * FROM produto WHERE id = ?",
            (id,)
        )
        produto = cursor.fetchone()

    return render_template(
        "editar_produto.html",
        produto=produto,
    )

@app.route("/atualizar_prod/<id>", methods=["POST"])
def atualizar_prod(id):

    novo_id = request.form["codigo"]
    novo_nome = request.form["nome"]
    nova_imagem = request.files.get("imagem")

    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # 🔹 Se enviou nova imagem
        if nova_imagem and nova_imagem.filename != "":
            imagem_bytes = nova_imagem.read()

            cursor.execute("""
                UPDATE produto
                SET id = ?, nome = ?, imagem = ?
                WHERE id = ?
            """, (novo_id, novo_nome, imagem_bytes, id))

        else:
            # 🔹 Se NÃO enviou imagem → mantém a antiga
            cursor.execute("""
                UPDATE produto
                SET id = ?, nome = ?
                WHERE id = ?
            """, (novo_id, novo_nome, id))

        conn.commit()

    return redirect(url_for("home"))

@app.route("/cadastrar_orc", methods=["GET", "POST"])
def cadastrar_orc():
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute("SELECT id, nome FROM produto")
        produtos = cursor.fetchall()
        
        if request.method == "POST":
            acao = request.form["acao"]

            if "id_orcamento" not in session:

                cliente = request.form.get("cliente", "").strip()
                cidade = request.form.get("cidade", "").strip()

                if not cliente or not cidade:
                    return "Cliente e cidade são obrigatórios", 400

                cursor.execute("""
                    INSERT INTO orcamento (cliente, cidade)
                    VALUES (?, ?)
                """, (cliente, cidade))

                session["id_orcamento"] = cursor.lastrowid
                session["cliente"] = cliente
                session["cidade"] = cidade

                conn.commit()

            id_orcamento = session["id_orcamento"]

            # 🔹 botão ADICIONAR
            if acao == "adicionar":
                
                nao_incluso = 1 if request.form.get("nao_incluso") else 0

                cursor.execute("""
                    INSERT INTO item_orcamento (
                        id_orcamento,
                        id_produto,
                        quantidade,
                        cor,
                        medida,
                        vidro,
                        unitario,
                        local,
                        nao_incluso
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id_orcamento,
                    request.form["id_produto"],
                    request.form["quantidade"],
                    request.form["cor"],
                    request.form["medida"],
                    request.form["vidro"],
                    float(request.form["unitario"]),
                    request.form["local"],
                    nao_incluso
                ))

                conn.commit()

                return redirect("/cadastrar_orc")

            # 🔹 botão SALVAR
            if acao == "salvar":

                cliente = session["cliente"]
                cidade = session["cidade"]
                id_orcamento = session["id_orcamento"]

                nao_incluso = 1 if request.form.get("nao_incluso") else 0
                
                cursor.execute("""
                    INSERT INTO item_orcamento (
                        id_orcamento,
                        id_produto,
                        quantidade,
                        cor,
                        medida,
                        vidro,
                        unitario,
                        local,
                        nao_incluso
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?,?)
                """, (
                    id_orcamento,
                    request.form["id_produto"],
                    request.form["quantidade"],
                    request.form["cor"],
                    request.form["medida"],
                    request.form["vidro"],
                    float(request.form["unitario"]),
                    request.form["local"],
                    nao_incluso
                ))

                conn.commit()

                # 🔹 buscar itens do banco
                cursor.execute("""
                    SELECT 
                        io.quantidade,
                        io.cor,
                        io.medida,
                        io.vidro,
                        io.unitario,
                        io.local,
                        p.id as produto_id,
                        p.nome,
                        p.imagem,
                        io.nao_incluso
                    FROM item_orcamento io
                    JOIN produto p ON p.id = io.id_produto
                    WHERE io.id_orcamento = ?
                """, (id_orcamento,))

                itens = cursor.fetchall()

                buffer = io.BytesIO()
                c = canvas.Canvas(buffer)

                # LOGO
                c.drawImage("static/logo.png", 95, 765, width=400, height=70)

                # CABEÇALHO
                cliente = session.get("cliente")
                cidade = session.get("cidade")

                c.drawString(50, 750, f"CLIENTE: {cliente}")
                c.drawString(56, 735, f"CIDADE: {cidade}")
                c.drawString(35, 710, "SEGUE ORÇAMENTO CONFORME SOLICITADO")
                c.drawString(0, 703, "-" * 200)

                y = 690
                quantidade_total = 0
                valor_total_orcamento = 0.0

                for item in itens:
                    qtd = int(item["quantidade"])
                    unitario = float(item["unitario"])
                    total = qtd * unitario
                    
                    if str(item["produto_id"]).startswith("-"):

                        if item["nao_incluso"] == 0:
                            quantidade_total += qtd
                            valor_total_orcamento += total

                            c.drawString(30, y, str(qtd))
                            c.drawString(55, y, item["nome"])

                            c.drawString(55, y - 20, f"COR: {item['cor']}")
                            c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")
                            c.drawString(55, y - 38, f"MATERIAL: {item['vidro']}")
                            c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                            c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")
                            c.drawString(0, y - 68, "." * 200)

                            if item["local"]:
                                c.drawString(440, y, f"LOCAL: {item['local']}")

                            imagem = ImageReader(io.BytesIO(item["imagem"]))
                            c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")
                            
                            y -= 85
                            if y < 80:
                                c.showPage()
                                y = 800
                                        
                        if item["nao_incluso"] == 1:
                            
                            c.drawString(30, y, str(qtd))
                            c.drawString(55, y, item["nome"])

                            c.drawString(55, y - 20, f"COR: {item['cor']}")
                            c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")
                            c.drawString(55, y - 38, f"VIDRO: {item['vidro']}")
                            c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                            c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")

                            if item["local"]:
                                c.drawString(440, y, f"LOCAL: {item['local']}")

                            imagem = ImageReader(io.BytesIO(item["imagem"]))
                            c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")
                            
                            c.setFillColor(minha_cor)
                            c.setFont("Helvetica-Oblique", 12)
                            c.drawString(20 , y - 75 , "Este item é apenas para comparação, não está incluso no valor total do orçamento.")
                            c.setFillColor(colors.black)
                            c.drawString(0, y - 80, "." * 200)
                            
                            y -= 98
                            if y < 80:
                                c.showPage()
                                y = 800
                                
                    else:
                        if item["nao_incluso"] == 0:
                            quantidade_total += qtd
                            valor_total_orcamento += total

                            c.drawString(30, y, str(qtd))
                            c.drawString(55, y, item["nome"])

                            c.drawString(55, y - 20, f"COR: {item['cor']}")
                            c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")
                            c.drawString(55, y - 38, f"VIDRO: {item['vidro']}")
                            c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                            c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")
                            c.drawString(0, y - 68, "." * 200)

                            if item["local"]:
                                c.drawString(440, y, f"LOCAL: {item['local']}")

                            imagem = ImageReader(io.BytesIO(item["imagem"]))
                            c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")
                            
                            y -= 85
                            if y < 80:
                                c.showPage()
                                y = 800
                                        
                        if item["nao_incluso"] == 1:
                            
                            c.drawString(30, y, str(qtd))
                            c.drawString(55, y, item["nome"])

                            c.drawString(55, y - 20, f"COR: {item['cor']}")
                            c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")
                            c.drawString(55, y - 38, f"VIDRO: {item['vidro']}")
                            c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                            c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")

                            if item["local"]:
                                c.drawString(440, y, f"LOCAL: {item['local']}")

                            imagem = ImageReader(io.BytesIO(item["imagem"]))
                            c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")
                            
                            c.setFillColor(minha_cor)
                            c.setFont("Helvetica-Oblique", 12)
                            c.drawString(20 , y - 75 , "Este item é apenas para comparação, não está incluso no valor total do orçamento.")
                            c.setFillColor(colors.black)
                            c.drawString(0, y - 80, "." * 200)
                            
                            y -= 98
                            if y < 80:
                                c.showPage()
                                y = 800

                c.drawString(35, y - 15, f"QUANTIDADE TOTAL DE ITENS: {quantidade_total}")
                c.drawString(
                    35, y - 30,
                    f"VALOR TOTAL DO ORÇAMENTO: R$ {fmt_money_br(valor_total_orcamento)}")
                
                c.save()
                buffer.seek(0)

                session.clear()

                return Response(
                    buffer.getvalue(),
                    mimetype="application/pdf",
                    headers={"Content-Disposition": "inline; filename=orcamento.pdf"}
                )

            
    return render_template("cadastrar_orc.html", produtos=produtos)
         
@app.route("/orc_cadastrados") 
def orc_cadastrados():
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orcamento")
        orcamentos = cursor.fetchall()

    return render_template("orc_cadastrados.html", orcamentos=orcamentos)

@app.route("/excluir_orcamento/<id_orcamento>", methods=["POST"])
def excluir_orcamento(id_orcamento):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute("DELETE FROM orcamento WHERE id_orcamento = ?", (id_orcamento,))
        conn.commit()

    return redirect("/orc_cadastrados")

@app.route("/excluir_item_orcamento/<int:item_id>", methods=["POST"])
def excluir_item_orcamento(item_id):

    import sqlite3

    conn = sqlite3.connect("instance/banco_trabalho.db", timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM item_orcamento WHERE id = ?", (item_id,))
    
    conn.commit()
    conn.close()

    return "", 200

@app.route("/editar_orcamento/<int:id_orcamento>")
def editar_orcamento(id_orcamento):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # 🔹 Buscar orçamento
        cursor.execute("""
            SELECT *
            FROM orcamento
            WHERE id_orcamento = ?
        """, (id_orcamento,))
        orcamento = cursor.fetchone()

        # 🔹 Buscar itens ORDENADOS corretamente
        cursor.execute("""
            SELECT 
                io.*,
                p.nome,
                p.imagem
            FROM item_orcamento io
            JOIN produto p ON p.id = io.id_produto
            WHERE io.id_orcamento = ?
            ORDER BY io.ordem ASC
        """, (id_orcamento,))
        itens = cursor.fetchall()

        # 🔹 Buscar produtos para o select
        cursor.execute("""
            SELECT *
            FROM produto
        """)
        produtos = cursor.fetchall()

    return render_template(
        "editar_orcamento.html",
        orcamento=orcamento,
        itens=itens,
        produtos=produtos
    )

@app.route("/atualizar_orcamento/<int:id_orcamento>", methods=["POST"])
def atualizar_orcamento(id_orcamento):

    conn = sqlite3.connect("instance/banco_trabalho.db", timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cliente = request.form.get("cliente")
    cidade = request.form.get("cidade")

    cursor.execute("""
        UPDATE orcamento
        SET cliente = ?, cidade = ?
        WHERE id_orcamento = ?
    """, (cliente, cidade, id_orcamento))

    # ==========================
    # 🔹 ATUALIZA ITENS EXISTENTES
    # ==========================

    ids = request.form.getlist("item_id[]")
    nao_incluso_lista = request.form.getlist("nao_incluso[]")

    for i in range(len(ids)):

        marcado = 1 if str(ids[i]) in nao_incluso_lista else 0

        cursor.execute("""
            UPDATE item_orcamento
            SET quantidade = ?, 
                cor = ?, 
                medida = ?, 
                vidro = ?, 
                unitario = ?, 
                local = ?, 
                nao_incluso = ?
            WHERE id = ? AND id_orcamento = ?
        """, (
            request.form.getlist("quantidade[]")[i],
            request.form.getlist("cor[]")[i],
            request.form.getlist("medida[]")[i],
            request.form.getlist("vidro[]")[i],
            float(request.form.getlist("unitario[]")[i] or 0),
            request.form.getlist("local[]")[i],
            marcado,
            ids[i],
            id_orcamento
        ))

    # ==========================
    # 🔹 INSERÇÃO DE NOVOS ITENS
    # ==========================

    novos_ids = request.form.getlist("novo_id_produto[]")
    referencias = request.form.getlist("inserir_depois_id[]")
    novo_nao_incluso_lista = request.form.getlist("novo_nao_incluso[]")

    for i in range(len(novos_ids)):

        id_produto = novos_ids[i].strip()

        if not id_produto:
            continue

        item_referencia = referencias[i]
        marcado = 1 if str(i) in novo_nao_incluso_lista else 0

        quantidade = request.form.getlist("novo_quantidade[]")[i]
        cor = request.form.getlist("novo_cor[]")[i]
        medida = request.form.getlist("novo_medida[]")[i]
        vidro = request.form.getlist("novo_vidro[]")[i]
        unitario = float(request.form.getlist("novo_unitario[]")[i] or 0)
        local = request.form.getlist("novo_local[]")[i]

        # 🔹 Define ordem base
        if item_referencia and item_referencia.isdigit():

            item_referencia = int(item_referencia)

            cursor.execute("""
                SELECT ordem
                FROM item_orcamento
                WHERE id = ? AND id_orcamento = ?
            """, (item_referencia, id_orcamento))

            resultado = cursor.fetchone()

            if resultado and resultado["ordem"] is not None:

                ordem_base = resultado["ordem"] + 1

                # 🔥 DESLOCA ITENS ABAIXO
                cursor.execute("""
                    UPDATE item_orcamento
                    SET ordem = ordem + 1
                    WHERE id_orcamento = ?
                    AND ordem >= ?
                """, (id_orcamento, ordem_base))

            else:
                cursor.execute("""
                    SELECT COALESCE(MAX(ordem),0)+1 AS nova_ordem
                    FROM item_orcamento
                    WHERE id_orcamento = ?
                """, (id_orcamento,))
                ordem_base = cursor.fetchone()["nova_ordem"]

        else:
            cursor.execute("""
                SELECT COALESCE(MAX(ordem),0)+1 AS nova_ordem
                FROM item_orcamento
                WHERE id_orcamento = ?
            """, (id_orcamento,))
            ordem_base = cursor.fetchone()["nova_ordem"]

        # 🔹 INSERT FINAL
        cursor.execute("""
            INSERT INTO item_orcamento
            (id_orcamento, id_produto, quantidade, cor, medida, vidro, unitario, local, ordem, nao_incluso)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_orcamento,
            id_produto,
            quantidade,
            cor,
            medida,
            vidro,
            unitario,
            local,
            ordem_base,
            marcado
        ))
 
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM item_orcamento
        WHERE ordem IS NULL
    """)
    if cursor.fetchone()["total"] > 0:
        raise Exception("ERRO: Existe item com ordem NULL")

    conn.commit()
    conn.close()

    return redirect(url_for("editar_orcamento", id_orcamento=id_orcamento))

@app.route("/gerar_pdf/<int:id_orcamento>")
def gerar_pdf(id_orcamento):

    conn = sqlite3.connect("instance/banco_trabalho.db", timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # 🔹 Buscar itens
    cursor.execute("""
        SELECT p.nome, p.id as produto_id, i.quantidade, i.cor, i.medida, 
               i.vidro, i.unitario, i.local, p.imagem, i.nao_incluso
        FROM item_orcamento i
        JOIN produto p ON p.id = i.id_produto
        WHERE i.id_orcamento = ?
        ORDER BY i.ordem
    """, (id_orcamento,))

    itens = cursor.fetchall()
    
    cursor.execute("""
        SELECT cliente, cidade
        FROM orcamento
        WHERE id_orcamento = ?
    """, (id_orcamento,))

    orcamento = cursor.fetchone()

    cliente = orcamento["cliente"]
    cidade = orcamento["cidade"]
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)

    c.drawImage("static/logo.png", 95, 765, width=400, height=70)

    # CABEÇALHO

    c.drawString(50, 750, f"CLIENTE: {cliente}")
    c.drawString(56, 735, f"CIDADE: {cidade}")
    c.drawString(35, 710, "SEGUE ORÇAMENTO CONFORME SOLICITADO")
    c.drawString(0, 703, "-" * 200)

    y = 690
    quantidade_total = 0
    valor_total_orcamento = 0.0

    for item in itens:
        qtd = int(item["quantidade"])
        unitario = float(item["unitario"])
        total = qtd * unitario

        if str(item["produto_id"]).startswith("-"):

            if item["nao_incluso"] == 0:
                quantidade_total += qtd
                valor_total_orcamento += total

                c.drawString(30, y, str(qtd))
                c.drawString(55, y, item["nome"])

                c.drawString(55, y - 20, f"COR: {item['cor']}")
                c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")
                c.drawString(55, y - 38, f"MATERIAL: {item['vidro']}")
                c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")
                c.drawString(0, y - 68, "." * 200)

                if item["local"]:
                    c.drawString(440, y, f"LOCAL: {item['local']}")

                imagem = ImageReader(io.BytesIO(item["imagem"]))
                c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")
                
                y -= 85
                if y < 80:
                    c.showPage()
                    y = 800
                            
            if item["nao_incluso"] == 1:
                
                c.drawString(30, y, str(qtd))
                c.drawString(55, y, item["nome"])

                c.drawString(55, y - 20, f"COR: {item['cor']}")
                c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")
                c.drawString(55, y - 38, f"VIDRO: {item['vidro']}")
                c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")

                if item["local"]:
                    c.drawString(440, y, f"LOCAL: {item['local']}")

                imagem = ImageReader(io.BytesIO(item["imagem"]))
                c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")
                
                c.setFillColor(minha_cor)
                c.setFont("Helvetica-Oblique", 12)
                c.drawString(20 , y - 75 , "Este item é apenas para comparação, não está incluso no valor total do orçamento.")
                c.setFillColor(colors.black)
                c.drawString(0, y - 80, "." * 200)
                
                y -= 98
                if y < 80:
                    c.showPage()
                    y = 800
                    
        else:
            if item["nao_incluso"] == 0:
                quantidade_total += qtd
                valor_total_orcamento += total

                c.drawString(30, y, str(qtd))
                c.drawString(55, y, item["nome"])

                c.drawString(55, y - 20, f"COR: {item['cor']}")
                c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")
                c.drawString(55, y - 38, f"VIDRO: {item['vidro']}")
                c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")
                c.drawString(0, y - 68, "." * 200)

                if item["local"]:
                    c.drawString(440, y, f"LOCAL: {item['local']}")

                imagem = ImageReader(io.BytesIO(item["imagem"]))
                c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")
                
                y -= 85
                if y < 80:
                    c.showPage()
                    y = 800
                            
            if item["nao_incluso"] == 1:
                
                c.drawString(30, y, str(qtd))
                c.drawString(55, y, item["nome"])

                c.drawString(55, y - 20, f"COR: {item['cor']}")
                c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")
                c.drawString(55, y - 38, f"VIDRO: {item['vidro']}")
                c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")

                if item["local"]:
                    c.drawString(440, y, f"LOCAL: {item['local']}")

                imagem = ImageReader(io.BytesIO(item["imagem"]))
                c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")
                
                c.setFillColor(minha_cor)
                c.setFont("Helvetica-Oblique", 12)
                c.drawString(20 , y - 75 , "Este item é apenas para comparação, não está incluso no valor total do orçamento.")
                c.setFillColor(colors.black)
                c.drawString(0, y - 80, "." * 200)
                
                y -= 98
                if y < 80:
                    c.showPage()
                    y = 800

    c.drawString(35, y - 15, f"QUANTIDADE TOTAL DE ITENS: {quantidade_total}")
    c.drawString(35, y - 30, f"VALOR TOTAL DO ORÇAMENTO: R$ {fmt_money_br(valor_total_orcamento)}")
    c.save()
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=orcamento.pdf"}
    )

@app.route("/finalizar_orcamento/<int:id_orcamento>", methods=["GET", "POST"])
def finalizar_orcamento(id_orcamento):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        if request.method == "POST":
            cursor.execute("""
                UPDATE orcamento
                SET cliente = ?
                WHERE id_orcamento = ?
            """, (
                request.form["cliente"],
                id_orcamento
            ))
            conn.commit()

        cursor.execute(
            "SELECT * FROM orcamento WHERE id_orcamento = ?",
            (id_orcamento,)
        )
        orcamento = cursor.fetchone()

        # 🔥 AQUI ESTÁ A ÚNICA ALTERAÇÃO REAL
        cursor.execute("""
            SELECT 
                io.*,
                p.nome,
                p.id as produto_id
            FROM item_orcamento io
            JOIN produto p ON p.id = io.id_produto
            WHERE io.id_orcamento = ?
            ORDER BY io.ordem ASC
        """, (id_orcamento,))
        itens = cursor.fetchall()

    if request.method == "POST":

        session["cliente"] = orcamento["cliente"]
        session["cidade"] = orcamento["cidade"]

        session["cpf"] = request.form["cpf"]
        session["endereco"] = request.form["endereco"]
        session["bairro"] = request.form["bairro"]
        session["cep"] = request.form["cep"]
        session["telefone"] = request.form["telefone"]
        session["data"] = request.form["data"]
        session["negociado"] = request.form.get("negociado", "")
        session["entrada"] = request.form.get("entrada", "")
        session["condicoes"] = request.form.get("condicoes", "").strip()
        session["prazo"] = request.form.get("prazo", "")

        # 🔥 Agora vai salvo já ordenado
        session["itens"] = [dict(item) for item in itens]

        return redirect(url_for("gerar_pdf_completo"))

    return render_template(
        "finalizar_orcamento.html",
        orcamento=orcamento
    )

@app.route("/gerar_pdf_completo")
def gerar_pdf_completo():
    conn = sqlite3.connect("instance/banco_trabalho.db")
    cursor = conn.cursor()

    cliente = session.get("cliente")
    cidade = session.get("cidade")
    cpf = session.get("cpf")
    endereco = session.get("endereco")
    bairro = session.get("bairro")
    cep = session.get("cep")
    telefone = session.get("telefone")
    data = session.get("data")
    negociado = session.get("negociado", "")
    entrada = session.get("entrada", "")
    condicoes = session.get("condicoes", "")
    prazo = session.get("prazo", "")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)

    # LOGO
    c.drawImage("static/logo.png", 95, 765, width=400, height=70)

    # CABEÇALHO
    c.drawString(20, 750, f"CLIENTE: {cliente}")
    c.drawString(325, 750, f"CPF/CNPJ: {cpf}")
    c.drawString(20, 733, f"ENDEREÇO: {endereco}")
    c.drawString(20, 715, f"BAIRRO: {bairro}")
    c.drawString(20, 698, f"CIDADE: {cidade}")
    c.drawString(325, 698, f"CEP: {cep}")
    c.drawString(20, 681, f"TELEFONE: {telefone}")
    c.drawString(20, 664, f"DATA: {data}")
    c.drawString(20, 638, "SEGUE O PEDIDO")
    c.drawString(0, 631, "-" * 200)

    y = 618
    quantidade_total = 0
    valor_total_orcamento = 0.0

    for item in session["itens"]:
        qtd = int(item["quantidade"])
        unitario = float(item["unitario"])
        total = qtd * unitario

        quantidade_total += qtd
        valor_total_orcamento += total
        
        if str(item["produto_id"]).startswith("-"):

            text = c.beginText(30, y)
            text.textOut(str(item["quantidade"]))
            c.drawText(text)

            text = c.beginText(55, y)
            text.textOut(item["nome"])
            c.drawText(text)

            text = c.beginText(55, y - 20)
            text.setFont("Helvetica-Bold", 12)
            text.textOut("COR: ")
            text.setFont("Helvetica", 12)
            text.textOut(item["cor"])
            c.drawText(text)

            text = c.beginText(205, y - 20)
            text.setFont("Helvetica-Bold", 12)
            text.textOut("MEDIDA: ")
            text.setFont("Helvetica", 12)
            text.textOut(item["medida"])
            c.drawText(text)

            text = c.beginText(55, y - 38)
            text.setFont("Helvetica-Bold", 12)
            text.textOut("MATERIAL: ")
            text.setFont("Helvetica", 12)
            text.textOut(item["vidro"])
            c.drawText(text)

            text = c.beginText(55, y - 55)
            text.setFont("Helvetica-Bold", 12)
            text.textOut("VALOR UNIT: ")
            text.setFont("Helvetica", 12)
            text.textOut(f"R$ {fmt_money_br(unitario)}")
            c.drawText(text)

            if item["local"].strip():
                text = c.beginText(440, y)
                text.setFont("Helvetica-Bold", 12)
                text.textOut("LOCAL: ")
                text.setFont("Helvetica", 12)
                text.textOut(item["local"])
                c.drawText(text)

            text = c.beginText(300, y - 55)
            text.setFont("Helvetica-Bold", 13)
            text.textOut(f"TOTAL: R$ {fmt_money_br(total)}")
            c.drawText(text)

            text = c.beginText(0, y - 70)
            text.setFont("Helvetica", 11)
            text.textOut("." * 250)
            c.drawText(text)

            cursor.execute(
                "SELECT imagem FROM produto WHERE id = ?",
                (item["id_produto"],)
            )
            img = cursor.fetchone()[0]

            imagem = ImageReader(io.BytesIO(img))
            c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")

            y -= 85
            if y < 80:
                c.showPage()
                y = 800
                
        else:
            text = c.beginText(30, y)
            text.textOut(str(item["quantidade"]))
            c.drawText(text)

            text = c.beginText(55, y)
            text.textOut(item["nome"])
            c.drawText(text)

            text = c.beginText(55, y - 20)
            text.setFont("Helvetica-Bold", 12)
            text.textOut("COR: ")
            text.setFont("Helvetica", 12)
            text.textOut(item["cor"])
            c.drawText(text)

            text = c.beginText(205, y - 20)
            text.setFont("Helvetica-Bold", 12)
            text.textOut("MEDIDA: ")
            text.setFont("Helvetica", 12)
            text.textOut(item["medida"])
            c.drawText(text)

            text = c.beginText(55, y - 38)
            text.setFont("Helvetica-Bold", 12)
            text.textOut("VIDRO: ")
            text.setFont("Helvetica", 12)
            text.textOut(item["vidro"])
            c.drawText(text)

            text = c.beginText(55, y - 55)
            text.setFont("Helvetica-Bold", 12)
            text.textOut("VALOR UNIT: ")
            text.setFont("Helvetica", 12)
            text.textOut(f"R$ {fmt_money_br(unitario)}")
            c.drawText(text)

            if item["local"].strip():
                text = c.beginText(440, y)
                text.setFont("Helvetica-Bold", 12)
                text.textOut("LOCAL: ")
                text.setFont("Helvetica", 12)
                text.textOut(item["local"])
                c.drawText(text)

            text = c.beginText(300, y - 55)
            text.setFont("Helvetica-Bold", 13)
            text.textOut(f"TOTAL: R$ {fmt_money_br(total)}")
            c.drawText(text)

            text = c.beginText(0, y - 70)
            text.setFont("Helvetica", 11)
            text.textOut("." * 250)
            c.drawText(text)

            cursor.execute(
                "SELECT imagem FROM produto WHERE id = ?",
                (item["id_produto"],)
            )
            img = cursor.fetchone()[0]

            imagem = ImageReader(io.BytesIO(img))
            c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")

            y -= 85
            if y < 80:
                c.showPage()
                y = 800

    c.setFont("Helvetica-Bold", 12)
    c.drawString(35, y - 5, f"TOTAL DE ITENS: {quantidade_total}")

    c.setFont("Helvetica-Bold", 15)
    c.drawString(
        35, y - 30,
        f"TOTAL DO ORÇAMENTO: R$ {fmt_money_br(valor_total_orcamento)}")

    c.setFont("Helvetica-Bold", 13)
    c.drawString(20, y - 60, negociado)
    
    c.setFont("Times-Bold", 12)
    c.drawString(21, y - 85, "Condição de pagamento: ")
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(200, y - 85, f"Entrada: R$ {entrada}")

    # TEXTO LIVRE (multilinha com quebra de página automática)
    text = c.beginText(200, y - 100)
    text.setFont("Helvetica-Bold", 11)

    y_min = 20  # limite inferior da página (ajuste se quiser)

    for linha in condicoes.splitlines():

        # Se não couber mais na página
        if text.getY() <= y_min:
            c.drawText(text)
            c.showPage()

            # reinicia o texto na nova página
            text = c.beginText(200, 795)
            text.setFont("Helvetica-Bold", 11)

        text.textLine(linha)

    c.drawText(text)

    # AJUSTE DINÂMICO DO Y FINAL
    y = text.getY() - 10

    if y < 80:
        c.showPage()
        y = 900

    c.setFont("Times-Bold", 11)
    c.drawString(20, y, "Prazo de entrega: ")
    
    c.setFont("Helvetica", 10)
    c.drawString(105, y, f"{prazo} a contar da data da medição oficial dos itens relacionados no pedido")
    
    c.setFont("Times-Bold", 12)
    c.drawString(21, y-28, "Considerações Gerais:")
    y -= 18
    
    # precisamos de ~60px de espaço para esse bloco
    c.setFont("Times-Roman", 11)

    y -= 30

    linhas = [
        "- Garantia de colocação até um (01) ano após a instalação (não cobre quebra de vidros ou mau uso);",
        "- Horário de instalação de segunda à sexta-feira das 07h às 17h. Para colocação aos sábados ou fora deste horário, ",
        "somente mediante consulta;",
        "- O cliente deverá demarcar a posição do encanamento nos banheiros, lavação, cozinha, ou em qualquer outro ambiente,",
        "onde possa passar algum cano de água, eletroduto ou tubulação de gás – sendo que a Testo Vidros não se responsabiliza em ",
        "casos de furação dos mesmos;",
        "- Para a medição oficial, caso haja a intenção de aplicar massa corrida, esta deverá estar aplicada antes da medição;",
        "- Para a colocação, o vão deverá estar com o reboco seco pelo menos 48 horas e com pelo menos uma de mão de tinta aplicada;",
        "- As aberturas deverão estar perfeitamente requadradas (esquadro), caso contrário a qualidade de colocação poderá ficar ",
        "prejudicada;",
        "- Nos casos em que o cliente vai abrir vão ou retirar janelas velhas para colocação de janelas em vidro temperado novas, deverá",
        "ser combinada a data de colocação de vidros com vinte (20 dias) de antecedência;",
        "- Este pedido não comtempla ART (Assinatura e Responsabilidade Técnica) em nenhum dos itens. Se necessária por exigência ",
        "dos bombeiros, será cobrada a parte;",
        "- Após a medição definitiva, os vidros deverão ser instalados em até 60 dias. Após esse período a Testo Vidros não se ",
        "responsabiliza por eventuais danos causados ao vidro devido ao tempo de estocagem.",
        "Assinado este, aceito e declaro estar de acordo com os itens acima descritos."
        
        ]

    for linha in linhas:
        # se essa linha não couber, quebra a página
        if y < 20:
            c.showPage()
            y = 810
            c.setFont("Times-Roman", 11)

        c.drawString(20, y, linha)
        y -= 15

    c.setFont("Helvetica", 11)
    c.drawString(48, y-70, "______________________________")
    
    c.drawImage("static/luan.png", 330, y-68, width=100, height=35)
    
    c.setFont("Helvetica", 11)
    c.drawString(300, y-70, "______________________________")
    c.drawString(303, y-85, "Testo Vidros 30.910.991/0001-11")

    texto = cliente + "  CPF/CNPJ - " + cpf
    x_inicial = 48
    largura_max = 130  # limite máximo de X
    altura_linha = 14

    linhas = simpleSplit(texto, "Helvetica", 10, largura_max)

    for linha in linhas:
        if y < 80:
            c.showPage()
            y = 900
            c.setFont("Times-Roman", 11)

        c.drawString(x_inicial, y-90, linha)
        y -= altura_linha
        
    c.save()
    buffer.seek(0)
    
    conn.commit()
    conn.close()

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=orcamento.pdf"}
    )
    
        
if __name__ == "__main__":
    app.run(debug=True) 