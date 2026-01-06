from flask import Flask, render_template, redirect, request, session, Response, url_for
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import sqlite3 
import io
from reportlab.lib.utils import simpleSplit

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
        id_orcamento INTEGER NOT NULL,
        id_produto TEXT NOT NULL,
        quantidade INTEGER NOT NULL,
        cor TEXT,
        medida TEXT,
        vidro TEXT,
        unitario REAL,
        local TEXT,
        FOREIGN KEY (id_orcamento) REFERENCES orcamento(id_orcamento) ON DELETE CASCADE,
        FOREIGN KEY (id_produto) REFERENCES produto(id)
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

                cursor.execute("""
                    INSERT INTO item_orcamento (
                        id_orcamento,
                        id_produto,
                        quantidade,
                        cor,
                        medida,
                        vidro,
                        unitario,
                        local
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id_orcamento,
                    request.form["id_produto"],
                    request.form["quantidade"],
                    request.form["cor"],
                    request.form["medida"],
                    request.form["vidro"],
                    float(request.form["unitario"]),
                    request.form["local"]
                ))

                conn.commit()

                return redirect("/cadastrar_orc")

            # 🔹 botão SALVAR
            if acao == "salvar":

                cliente = session["cliente"]
                cidade = session["cidade"]
                id_orcamento = session["id_orcamento"]

                # 🔹 salva o item atual antes de gerar o PDF
                cursor.execute("""
                    INSERT INTO item_orcamento (
                        id_orcamento,
                        id_produto,
                        quantidade,
                        cor,
                        medida,
                        vidro,
                        unitario,
                        local
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id_orcamento,
                    request.form["id_produto"],
                    request.form["quantidade"],
                    request.form["cor"],
                    request.form["medida"],
                    request.form["vidro"],
                    float(request.form["unitario"]),
                    request.form["local"]
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
                        p.nome,
                        p.imagem,
                        p.id
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

                c.drawString(35, y - 5, f"QUANTIDADE TOTAL DE ITENS: {quantidade_total}")
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

@app.route("/editar_orcamento/<int:id_orcamento>")
def editar_orcamento(id_orcamento):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # orçamento
        cursor.execute(
            "SELECT * FROM orcamento WHERE id_orcamento = ?",
            (id_orcamento,)
        )
        orcamento = cursor.fetchone()

        # itens do orçamento (com rowid)
        cursor.execute("""
            SELECT 
                io.rowid AS rowid,
                io.*,
                p.nome
            FROM item_orcamento io
            JOIN produto p ON p.id = io.id_produto
            WHERE io.id_orcamento = ?
        """, (id_orcamento,))
        itens = cursor.fetchall()

        # produtos para adicionar novos itens
        cursor.execute("SELECT * FROM produto")
        produtos = cursor.fetchall()

    return render_template(
        "editar_orcamento.html",
        orcamento=orcamento,
        itens=itens,
        produtos=produtos
    )

@app.route("/atualizar_orcamento/<int:id_orcamento>", methods=["POST"])
def atualizar_orcamento(id_orcamento):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # 🔹 atualizar orçamento
        cursor.execute("""
            UPDATE orcamento
            SET cliente = ?, cidade = ?
            WHERE id_orcamento = ?
        """, (
            request.form["cliente"],
            request.form["cidade"],
            id_orcamento
        ))

        # 🔹 atualizar itens existentes
        for (
            item_id,
            quantidade,
            cor,
            medida,
            vidro,
            unitario,
            local
        ) in zip(
            request.form.getlist("item_id[]"),
            request.form.getlist("quantidade[]"),
            request.form.getlist("cor[]"),
            request.form.getlist("medida[]"),
            request.form.getlist("vidro[]"),
            request.form.getlist("unitario[]"),
            request.form.getlist("local[]")
        ):
            cursor.execute("""
                UPDATE item_orcamento
                SET
                    quantidade = ?,
                    cor = ?,
                    medida = ?,
                    vidro = ?,
                    unitario = ?,
                    local = ?
                WHERE rowid = ?
            """, (
                quantidade,
                cor,
                medida,
                vidro,
                float(unitario),
                local,
                item_id
            ))

        # 🔹 inserir novos itens
        for (
            id_produto,
            quantidade,
            cor,
            medida,
            vidro,
            unitario,
            local
        ) in zip(
            request.form.getlist("novo_id_produto[]"),
            request.form.getlist("novo_quantidade[]"),
            request.form.getlist("novo_cor[]"),
            request.form.getlist("novo_medida[]"),
            request.form.getlist("novo_vidro[]"),
            request.form.getlist("novo_unitario[]"),
            request.form.getlist("novo_local[]")
        ):
            cursor.execute("""
                INSERT INTO item_orcamento (
                    id_orcamento,
                    id_produto,
                    quantidade,
                    cor,
                    medida,
                    vidro,
                    unitario,
                    local
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                id_orcamento,
                id_produto,
                quantidade,
                cor,
                medida,
                vidro,
                float(unitario),
                local
            ))

        # ✅ COMMIT REAL
        conn.commit()
        
        cursor.execute(
            "SELECT cliente, cidade FROM orcamento WHERE id_orcamento = ?",
            (id_orcamento,)
        )
        
        orcamento = cursor.fetchone()

        # 🔹 dados atualizados para PDF
        cursor.execute("""
            SELECT 
                io.quantidade,
                io.cor,
                io.medida,
                io.vidro,
                io.unitario,
                io.local,
                p.nome,
                p.imagem
            FROM item_orcamento io
            JOIN produto p ON p.id = io.id_produto
            WHERE io.id_orcamento = ?
        """, (id_orcamento,))
        itens = cursor.fetchall()


    # 🔹 PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)

    # LOGO
    c.drawImage("static/logo.png", 95, 765, width=400, height=70)

    # CABEÇALHO
    cliente = orcamento["cliente"]
    cidade = orcamento["cidade"]

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

    c.drawString(35, y - 5, f"QUANTIDADE TOTAL DE ITENS: {quantidade_total}")
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
    
@app.route("/finalizar_orcamento/<int:id_orcamento>", methods=["GET", "POST"])
def finalizar_orcamento(id_orcamento):
    with sqlite3.connect("instance/banco_trabalho.db") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if request.method == "POST":
            # 🔹 atualiza o cliente (se foi alterado)
            cursor.execute("""
                UPDATE orcamento
                SET cliente = ?
                WHERE id_orcamento = ?
            """, (
                request.form["cliente"],
                id_orcamento
            ))
            conn.commit()

        # 🔹 busca orçamento atualizado
        cursor.execute(
            "SELECT * FROM orcamento WHERE id_orcamento = ?",
            (id_orcamento,)
        )
        orcamento = cursor.fetchone()

        # 🔹 itens do orçamento
        cursor.execute("""
            SELECT 
                io.*,
                p.nome
            FROM item_orcamento io
            JOIN produto p ON p.id = io.id_produto
            WHERE io.id_orcamento = ?
        """, (id_orcamento,))
        itens = cursor.fetchall()

    if request.method == "POST":
        # 🔹 salva dados na sessão para o PDF
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

    return render_template(
        "finalizar_orcamento.html",
        orcamento=orcamento
    )

@app.route("/gerar_pdf_completo")
def gerar_pdf_completo():

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
    c.drawString(325, 698, f"CIDADE: {cep}")
    c.drawString(20, 681, f"TELEFONE: {telefone}")
    c.drawString(20, 664, f"DATA: {data}")
    c.drawString(20, 635, "SEGUE O PEDIDO")
    c.drawString(0, 628, "-" * 200)

    y = 618
    quantidade_total = 0
    valor_total_orcamento = 0.0

    for item in session["itens"]:
        qtd = int(item["quantidade"])
        unitario = float(item["unitario"])
        total = qtd * unitario

        quantidade_total += qtd
        valor_total_orcamento += total

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

        conn = sqlite3.connect("instance/banco_trabalho.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT imagem FROM produto WHERE id = ?",
            (item["id_produto"],)
        )
        img = cursor.fetchone()[0]
        conn.close()

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
        "- Para a colocação, o vão deverá estar com o reboco seco pelo menos 48 horas e com pelo menos uma de mão de tinta ou massa ",
        "corrida aplicada;",
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
    c.drawString(48, y-70, "____________________")
    
    c.drawImage("static/luan.png", 330, y-68, width=100, height=35)
    
    c.setFont("Helvetica", 11)
    c.drawString(300, y-70, "____________________________")
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

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=orcamento.pdf"}
    )

        
        

        

    

    
    
    




    
    
    
    
    
    
    
    
    
    
    
    
    c.save()
    buffer.seek(0)

    session.clear()

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=pedido_final.pdf"}
    ) 
        
if __name__ == "__main__":
    app.run(debug=True) 