from flask import Flask, render_template, redirect, request, session, Response, url_for
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
import os
from reportlab.lib.utils import simpleSplit
from reportlab.lib import colors
from reportlab.lib.colors import Color
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL") 

app = Flask(__name__)
app.secret_key = "Trabalhoooooooooooooooooooooo"

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

minha_cor = Color(0.7, 0.1, 0.2) 

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS produto (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            imagem BYTEA
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orcamento (
            id_orcamento SERIAL PRIMARY KEY,
            cliente TEXT NOT NULL,
            cidade TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS item_orcamento (
            id SERIAL PRIMARY KEY,
            id_orcamento INTEGER,
            id_produto TEXT,
            nao_incluso BOOLEAN DEFAULT FALSE,
            quantidade INTEGER,
            cor TEXT,
            medida TEXT,
            vidro TEXT,
            unitario NUMERIC(10,2),
            local TEXT,
            ordem INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(id_orcamento) REFERENCES orcamento(id_orcamento) ON DELETE CASCADE,
            FOREIGN KEY(id_produto) REFERENCES produto(id) ON UPDATE CASCADE
        );
        """)

        conn.commit()
   
init_db()

def fmt_money_br(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def normalizar_ordem(id_orcamento, cursor):
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id FROM item_orcamento WHERE id_orcamento = %s ORDER BY ordem, id """, (id_orcamento,))

        itens = cursor.fetchall()

        nova_ordem = 1
        for item in itens:
            cursor.execute("""UPDATE item_orcamento SET ordem = %s WHERE id = %s""", (nova_ordem, item["id"]))
            nova_ordem += 1
    
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/prod_cadastrados')
def prod_cadastrados():
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM produto")
        produtos = cursor.fetchall()

    return render_template("prod_cadastrados.html", produtos=produtos)

@app.route("/excluir_produto/<id>", methods=["POST"])
def excluir_produto(id):
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("DELETE FROM produto WHERE id = %s", (id,))
        conn.commit()

    return redirect("/prod_cadastrados")

@app.route('/imagem/<id>')
def imagem(id):
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT imagem FROM produto WHERE id = %s", (id,))

        img = cursor.fetchone()

        if img and img["imagem"]:
            return Response(bytes(img["imagem"]), mimetype="image/jpeg")

    return "", 404

@app.route("/cadastro_novo_prod", methods=['GET', 'POST'])
def cadastro_novo_prod():

    if request.method == 'POST':

        codigo = request.form['id']
        nome = request.form['nome']

        imagem_file = request.files.get('imagem')
        imagem_bytes = None

        if imagem_file and imagem_file.filename != "":
            imagem_bytes = imagem_file.read()

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                INSERT INTO produto (id, nome, imagem) VALUES (%s, %s, %s) """, (codigo, nome, imagem_bytes))
            
            conn.commit()

    return render_template("cadastro_novo_prod.html")

@app.route("/editar_prod/<id>")
def editar_prod(id):
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # orçamento
        cursor.execute(
            "SELECT * FROM produto WHERE id = %s",(id,) )
        
        produto = cursor.fetchone()

    return render_template( "editar_produto.html", produto=produto,)

@app.route("/atualizar_prod/<id>", methods=["POST"])
def atualizar_prod(id):

    novo_id = request.form["codigo"]
    novo_nome = request.form["nome"]
    nova_imagem = request.files.get("imagem")

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 🔹 Se enviou nova imagem
        if nova_imagem and nova_imagem.filename != "":
            imagem_bytes = nova_imagem.read()

            cursor.execute(""" UPDATE produto SET nome = %s, imagem = %s WHERE id = %s """, (novo_nome, imagem_bytes, id))

        else:
            # 🔹 Se NÃO enviou imagem → mantém a antiga
            cursor.execute("""UPDATE produto SET id = %s, nome = %s WHERE id = %s """, (novo_id, novo_nome, id))

        conn.commit()

    return redirect(url_for("home"))

@app.route("/cadastrar_orc", methods=["GET", "POST"])
def cadastrar_orc():

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        session.clear()

        cursor.execute("SELECT id, nome FROM produto")
        produtos = cursor.fetchall()

        if request.method == "POST":

            acao = request.form["acao"]

            if "id_orcamento" not in session:

                cliente = request.form.get("cliente", "").strip()
                cidade = request.form.get("cidade", "").strip()

                if not cliente or not cidade:
                    return "Cliente e cidade são obrigatórios", 400

                cursor.execute("""INSERT INTO orcamento (cliente, cidade) VALUES (%s, %s) RETURNING id_orcamento""", (cliente, cidade))

                session["id_orcamento"] = cursor.fetchone()["id_orcamento"]
                session["cliente"] = cliente
                session["cidade"] = cidade

                conn.commit()

            id_orcamento = session["id_orcamento"]
            nao_incluso = 1 if request.form.get("nao_incluso") else 0

            if acao in ["adicionar", "salvar"]:

                cursor.execute("""
                    INSERT INTO item_orcamento (id_orcamento,id_produto,quantidade, cor,medida,vidro, unitario, local, nao_incluso
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (
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

                if acao == "adicionar":
                    return redirect("/cadastrar_orc")

                cursor.execute("""
                    SELECT io.quantidade, io.cor, io.medida, io.vidro,io.unitario,io.local,p.id as produto_id,p.nome,p.imagem,io.nao_incluso
                    FROM item_orcamento io JOIN produto p ON p.id = io.id_produto WHERE io.id_orcamento = %s """, (id_orcamento,))

                itens = cursor.fetchall()

                buffer = io.BytesIO()
                c = canvas.Canvas(buffer)

                c.drawImage("static/logo.png", 95, 765, width=400, height=70)

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

                    local = item["local"] or ""
                    img = item["imagem"]

                    if item["nao_incluso"] == 0:
                        quantidade_total += qtd
                        valor_total_orcamento += total

                    c.drawString(30, y, str(qtd))
                    c.drawString(55, y, item["nome"])

                    c.drawString(55, y - 20, f"COR: {item['cor']}")
                    c.drawString(205, y - 20, f"MEDIDA: {item['medida']}")

                    if str(item["produto_id"]).startswith("-"):
                        c.drawString(55, y - 38, f"MATERIAL: {item['vidro']}")
                    else:
                        c.drawString(55, y - 38, f"VIDRO: {item['vidro']}")

                    c.drawString(55, y - 55, f"VALOR UNIT: R$ {fmt_money_br(unitario)}")
                    c.drawString(300, y - 55, f"TOTAL: R$ {fmt_money_br(total)}")

                    if local:
                        c.drawString(440, y, f"LOCAL: {local}")

                    if img:
                        imagem_bytes = bytes(img)
                        imagem = ImageReader(io.BytesIO(imagem_bytes))
                        c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")

                    if item["nao_incluso"] == 1:

                        c.setFillColor(minha_cor)
                        c.setFont("Helvetica-Oblique", 12)
                        c.drawString(
                            20,
                            y - 75,
                            "Este item é apenas para comparação, não está incluso no valor total do orçamento."
                        )
                        c.setFillColor(colors.black)
                        c.setFont("Helvetica", 12)

                        c.drawString(0, y - 80, "." * 200)
                        y -= 98

                    else:

                        c.drawString(0, y - 68, "." * 200)
                        y -= 85

                    if y < 80:
                        c.showPage()
                        y = 800

                c.drawString(35, y - 15, f"QUANTIDADE TOTAL DE ITENS: {quantidade_total}")
                c.drawString(
                    35,
                    y - 30,
                    f"VALOR TOTAL DO ORÇAMENTO: R$ {fmt_money_br(valor_total_orcamento)}"
                )

                c.save()
                buffer.seek(0)
                session.clear()

                return Response( buffer.getvalue(), mimetype="application/pdf", headers={"Content-Disposition": "inline; filename=orcamento.pdf"} )

    return render_template("cadastrar_orc.html", produtos=produtos)
         
@app.route("/orc_cadastrados") 
def orc_cadastrados():
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM orcamento")
        orcamentos = cursor.fetchall()

    return render_template("orc_cadastrados.html", orcamentos=orcamentos)

@app.route("/excluir_orcamento/<id_orcamento>", methods=["POST"])
def excluir_orcamento(id_orcamento):
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("DELETE FROM orcamento WHERE id_orcamento = %s", (id_orcamento,))
        conn.commit()

    return redirect(url_for("orc_cadastrados"))

@app.route("/excluir_item_orcamento/<int:item_id>", methods=["POST"])
def excluir_item_orcamento(item_id):

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("DELETE FROM item_orcamento WHERE id = %s", (item_id,))
        conn.commit()

        return "", 200

@app.route("/editar_orcamento/<int:id_orcamento>")
def editar_orcamento(id_orcamento):

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(""" SELECT * FROM orcamento WHERE id_orcamento = %s """, (id_orcamento,))
        orcamento = cursor.fetchone()

        if not orcamento:
            return "Orçamento não encontrado", 404

        cursor.execute(""" SELECT io.*, p.nome, p.imagem FROM item_orcamento io JOIN produto p ON p.id = io.id_produto
            WHERE io.id_orcamento = %s ORDER BY io.ordem ASC """, (id_orcamento,))
        
        itens = cursor.fetchall()

        cursor.execute("SELECT * FROM produto")
        produtos = cursor.fetchall()

    return render_template( "editar_orcamento.html", orcamento=orcamento, itens=itens, produtos=produtos)

@app.route("/atualizar_orcamento/<int:id_orcamento>", methods=["POST"])
def atualizar_orcamento(id_orcamento):

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cliente = request.form.get("cliente", "").strip()
        cidade = request.form.get("cidade", "").strip()

        cursor.execute(""" UPDATE orcamento SET cliente = %s, cidade = %s WHERE id_orcamento = %s""", 
            (cliente, cidade, id_orcamento))

        ids = request.form.getlist("item_id[]")
        nao_incluso_lista = request.form.getlist("nao_incluso[]")

        for i in range(len(ids)):
            marcado = 1 if str(ids[i]) in nao_incluso_lista else 0

            cursor.execute(""" UPDATE item_orcamento SET quantidade = %s, cor = %s, medida = %s, vidro = %s, 
                    unitario = %s, local = %s, nao_incluso = %s
                WHERE id = %s AND id_orcamento = %s """, (
                request.form.getlist("quantidade[]")[i],
                request.form.getlist("cor[]")[i],
                request.form.getlist("medida[]")[i],
                request.form.getlist("vidro[]")[i],
                float(request.form.getlist("unitario[]")[i] or 0),
                request.form.getlist("local[]")[i],
                marcado,
                ids[i],
                id_orcamento))

        conn.commit()

    return redirect(url_for("editar_orcamento", id_orcamento=id_orcamento))

@app.route("/gerar_pdf/<int:id_orcamento>")
def gerar_pdf(id_orcamento):

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(""" SELECT p.nome, p.id as produto_id, i.quantidade, i.cor, i.medida, i.vidro, i.unitario, i.local,
                   p.imagem, i.nao_incluso
            FROM item_orcamento i JOIN produto p ON p.id = i.id_produto WHERE i.id_orcamento = %s ORDER BY i.ordem """, 
            (id_orcamento,))

        itens = cursor.fetchall()

        cursor.execute(""" SELECT cliente, cidade FROM orcamento WHERE id_orcamento = %s """, (id_orcamento,))

        orcamento = cursor.fetchone()

    if not orcamento:
        return "Orçamento não encontrado", 404

    cliente = orcamento["cliente"]
    cidade = orcamento["cidade"]

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)

    c.drawImage("static/logo.png", 95, 765, width=400, height=70)

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

        if item["local"]:
            c.drawString(440, y, f"LOCAL: {item['local']}")

        if item["imagem"]:
            imagem_bytes = bytes(item["imagem"])
            imagem = ImageReader(io.BytesIO(imagem_bytes))
            c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")

        if item["nao_incluso"] == 1:

            c.setFillColor(minha_cor)
            c.setFont("Helvetica-Oblique", 12)

            c.drawString( 20, y - 75, "Este item é apenas para comparação, não está incluso no valor total do orçamento.")
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

    return Response(buffer.getvalue(), mimetype="application/pdf", headers={"Content-Disposition": "inline; filename=orcamento.pdf"})
    
@app.route("/finalizar_orcamento/<int:id_orcamento>", methods=["GET", "POST"])
def finalizar_orcamento(id_orcamento):
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == "POST":
            cursor.execute(""" UPDATE orcamento SET cliente = %s WHERE id_orcamento = %s """, (request.form["cliente"], id_orcamento))
            conn.commit()

        cursor.execute("SELECT * FROM orcamento WHERE id_orcamento = %s", (id_orcamento,))
        orcamento = cursor.fetchone()

        cursor.execute("""SELECT io.*, p.nome, p.id as produto_id FROM item_orcamento io JOIN produto p ON p.id = io.id_produto
            WHERE io.id_orcamento = %s ORDER BY io.ordem ASC """, (id_orcamento,))
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
        session["itens"] = [dict(item) for item in itens]

        return redirect(url_for("gerar_pdf_completo"))

    return render_template("finalizar_orcamento.html", orcamento=orcamento)

@app.route("/gerar_pdf_completo")
def gerar_pdf_completo():
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

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

        c.drawImage("static/logo.png", 95, 765, width=400, height=70)
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

                cursor.execute("SELECT imagem FROM produto WHERE id = %s", (item["id_produto"],))
                row = cursor.fetchone()
                img = row["imagem"] if row else None

                if img:
                    imagem_bytes = bytes(img)
                    imagem = ImageReader(io.BytesIO(imagem_bytes))
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

                cursor.execute( "SELECT imagem FROM produto WHERE id = %s", (item["id_produto"],))
                row = cursor.fetchone()
                img = row["imagem"] if row else None

                if img:
                    imagem_bytes = bytes(img)
                    imagem = ImageReader(io.BytesIO(imagem_bytes))
                    c.drawImage(imagem, 455, y - 65, width=100, height=60, mask="auto")

                y -= 85
                if y < 80:
                    c.showPage()
                    y = 800

        c.setFont("Helvetica-Bold", 12)
        c.drawString(35, y - 5, f"TOTAL DE ITENS: {quantidade_total}")
        c.setFont("Helvetica-Bold", 15)
        c.drawString(35, y - 30, f"TOTAL DO ORÇAMENTO: R$ {fmt_money_br(valor_total_orcamento)}")
        c.setFont("Helvetica-Bold", 13)
        c.drawString(20, y - 60, negociado)
        c.setFont("Times-Bold", 12)
        c.drawString(21, y - 85, "Condição de pagamento: ")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(200, y - 85, f"Entrada: R$ {entrada}")
        
        text = c.beginText(200, y - 100)
        text.setFont("Helvetica-Bold", 11)

        y_min = 20  # limite inferior da página (ajuste se quiser)

        for linha in condicoes.splitlines():
            if text.getY() <= y_min:
                c.drawText(text)
                c.showPage()
                text = c.beginText(200, 795)
                text.setFont("Helvetica-Bold", 11)

            text.textLine(linha)
        c.drawText(text)

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

        return Response(buffer.getvalue(), mimetype="application/pdf", headers={"Content-Disposition": "inline; filename=orcamento.pdf"} )
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)