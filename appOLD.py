from flask import Flask, request, redirect, url_for, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///associacao.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ================= MODELOS UNIFICADOS =================

class Jogador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20))
    tipo = db.Column(db.String(10))  # SÓCIO / CONVIDADO

class Jogo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    adversario = db.Column(db.String(100))
    local = db.Column(db.String(100))
    valor_jogo = db.Column(db.Float, default=0)
    resumo_texto = db.Column(db.Text)
    craque_id = db.Column(db.Integer, db.ForeignKey('jogador.id'))
    
    # Relacionamentos
    participantes = db.relationship('Participacao', backref='jogo', cascade="all, delete-orphan")

class Participacao(db.Model):
    """Tabela central que une Jogador, Jogo, Financeiro e Estatísticas"""
    id = db.Column(db.Integer, primary_key=True)
    jogo_id = db.Column(db.Integer, db.ForeignKey('jogo.id'), nullable=False)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=False)
    
    # Presença e Financeiro
    confirmou = db.Column(db.Boolean, default=False)
    pagou = db.Column(db.Boolean, default=False)
    valor_pago = db.Column(db.Float, default=0)
    lancado_financeiro = db.Column(db.Boolean, default=False) # Evita duplicar no financeiro

    # Estatísticas
    gols = db.Column(db.Integer, default=0)
    expulso = db.Column(db.Boolean, default=False)

    jogador = db.relationship('Jogador')

class Financeiro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(15))  # MENSALIDADE / PARTIDA / DESPESA
    descricao = db.Column(db.String(100))
    valor = db.Column(db.Float)

# ================= TEMPLATE BASE =================
BASE_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Associação Esportiva</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    .card { border-radius: 12px; border: none; }
    .table-responsive { border-radius: 12px; overflow: hidden; }
  </style>
</head>
<body class="bg-light">
<nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4 shadow">
  <div class="container">
    <a class="navbar-brand fw-bold" href="/">🏆 ASSOCIAÇÃO</a>
    <div class="navbar-nav">
      <a class="nav-link" href="/jogadores">Atletas</a>
      <a class="nav-link" href="/associados">Mensalidades</a>
      <a class="nav-link" href="/jogos">Jogos</a>
      <a class="nav-link" href="/financeiro">Caixa</a>
    </div>
  </div>
</nav>
<div class="container">{{ content | safe }}</div>
</body>
</html>
"""

# ================= ROTAS PRINCIPAIS =================

@app.route('/')
def index():
    mensal = db.session.query(db.func.sum(Financeiro.valor)).filter(Financeiro.tipo=='MENSALIDADE').scalar() or 0
    partidas = db.session.query(db.func.sum(Financeiro.valor)).filter(Financeiro.tipo=='PARTIDA').scalar() or 0
    despesas = db.session.query(db.func.sum(Financeiro.valor)).filter(Financeiro.tipo=='DESPESA').scalar() or 0
    saldo = mensal + partidas - despesas
    
    content = f"""
    <div class='row g-3 text-center'>
      <div class='col-md-3'><div class='card p-3 shadow-sm bg-primary text-white'><h6>Saldo Geral</h6><h3>R$ {saldo:.2f}</h3></div></div>
      <div class='col-md-3'><div class='card p-3 shadow-sm bg-success text-white'><h6>Mensalidades</h6><h3>R$ {mensal:.2f}</h3></div></div>
      <div class='col-md-3'><div class='card p-3 shadow-sm bg-info text-white'><h6>Partidas</h6><h3>R$ {partidas:.2f}</h3></div></div>
      <div class='col-md-3'><div class='card p-3 shadow-sm bg-danger text-white'><h6>Despesas</h6><h3>R$ {despesas:.2f}</h3></div></div>
    </div>
    <div class='mt-4 p-4 bg-white rounded shadow-sm'>
        <h4>Bem-vindo ao Gestor da Associação</h4>
        <p class='text-muted'>Utilize o menu acima para gerenciar atletas, jogos e o caixa.</p>
    </div>
    """
    return render_template_string(BASE_HTML, content=content)

@app.route('/jogos', methods=['GET','POST'])
def jogos():
    if request.method == 'POST':
        novo_jogo = Jogo(
            data=date.fromisoformat(request.form['data']),
            adversario=request.form.get('adversario'),
            local=request.form.get('local'),
            valor_jogo=float(request.form.get('valor_jogo') or 0)
        )
        db.session.add(novo_jogo)
        db.session.flush() # Gera ID do jogo antes do commit final

        # Criar participações vazias para todos os jogadores ativos
        jogadores = Jogador.query.all()
        for j in jogadores:
            db.session.add(Participacao(jogo_id=novo_jogo.id, jogador_id=j.id))
        
        db.session.commit()
        return redirect(url_for('jogos'))

    lista_jogos = Jogo.query.order_by(Jogo.data.desc()).all()
    rows = ""
    for j in lista_jogos:
        rows += f"""
        <tr>
            <td>{j.data.strftime('%d/%m/%Y')}</td>
            <td>{j.adversario}</td>
            <td>{j.local}</td>
            <td>
                <a href='/presencas/{j.id}' class='btn btn-sm btn-outline-primary'>Presenças/Pagos</a>
                <a href='/resumo-jogo/{j.id}' class='btn btn-sm btn-outline-secondary'>Resumo Técnico</a>
            </td>
        </tr>"""

    content = f"""
    <h3>⚽ Gestão de Jogos</h3>
    <div class='card p-3 mb-4 shadow-sm'>
        <form method='post' class='row g-2'>
            <div class='col-md-2'><input type='date' name='data' class='form-control' required></div>
            <div class='col-md-4'><input name='adversario' placeholder='Adversário' class='form-control' required></div>
            <div class='col-md-3'><input name='local' placeholder='Local' class='form-control'></div>
            <div class='col-md-2'><input name='valor_jogo' placeholder='Valor Sugerido' class='form-control'></div>
            <div class='col-md-1'><button class='btn btn-success w-100'>+</button></div>
        </form>
    </div>
    <div class='table-responsive bg-white shadow-sm'>
        <table class='table table-hover mb-0'>
            <thead class='table-dark'><tr><th>Data</th><th>Adversário</th><th>Local</th><th>Ações</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    return render_template_string(BASE_HTML, content=content)

@app.route('/presencas/<int:jogo_id>', methods=['GET','POST'])
def presencas(jogo_id):
    jogo = Jogo.query.get_or_404(jogo_id)
    participacoes = Participacao.query.filter_by(jogo_id=jogo_id).all()

    if request.method == 'POST':
        for p in participacoes:
            p.confirmou = f'confirmou_{p.id}' in request.form
            p.pagou = f'pagou_{p.id}' in request.form
            p.valor_pago = float(request.form.get(f'valor_{p.id}') or 0)

            # Lógica Financeira: Só lança se pagou e ainda não foi lançado para este jogo
            if p.pagou and p.valor_pago > 0 and not p.lancado_financeiro:
                db.session.add(Financeiro(
                    data=date.today(),
                    tipo='PARTIDA',
                    descricao=f"Pgto Jogo {jogo.data} - {p.jogador.nome}",
                    valor=p.valor_pago
                ))
                p.lancado_financeiro = True
        
        # Adicionar Despesa do Jogo
        desc_despesa = request.form.get('desc_despesa')
        val_despesa = request.form.get('val_despesa')
        if desc_despesa and val_despesa:
            db.session.add(Financeiro(
                data=date.today(),
                tipo='DESPESA',
                descricao=f"Despesa Jogo {jogo.data}: {desc_despesa}",
                valor=float(val_despesa)
            ))

        db.session.commit()
        return redirect(url_for('presencas', jogo_id=jogo_id))

    rows = ""
    for p in participacoes:
        rows += f"""
        <tr>
            <td>{p.jogador.nome} <small class='text-muted'>({p.jogador.tipo})</small></td>
            <td><input type='checkbox' name='confirmou_{p.id}' {'checked' if p.confirmou else ''}></td>
            <td><input type='checkbox' name='pagou_{p.id}' {'checked' if p.pagou else ''}></td>
            <td><input type='number' step='0.01' name='valor_{p.id}' value='{p.valor_pago}' class='form-control form-control-sm'></td>
            <td>{'✅' if p.lancado_financeiro else '⏳'}</td>
        </tr>"""

    content = f"""
    <h4>📋 Presenças e Pagamentos: {jogo.adversario} ({jogo.data})</h4>
    <form method='post'>
        <div class='table-responsive shadow-sm bg-white mb-3'>
            <table class='table align-middle'>
                <thead class='table-secondary'><tr><th>Jogador</th><th>Confirmou?</th><th>Pagou?</th><th>Valor R$</th><th>Status</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        <div class='card p-3 mb-3 bg-light'>
            <h5>💸 Adicionar Despesa de Partida</h5>
            <div class='row g-2'>
                <div class='col-md-8'><input name='desc_despesa' placeholder='Ex: Árbitro, Água, Lavagem' class='form-control'></div>
                <div class='col-md-4'><input type='number' step='0.01' name='val_despesa' placeholder='Valor R$' class='form-control'></div>
            </div>
        </div>
        <button class='btn btn-primary btn-lg shadow'>Salvar Alterações Financeiras</button>
    </form>
    
    <script>
        // Mostrar/ocultar campo de gols quando checkbox é marcado
        document.addEventListener('DOMContentLoaded', function() {
            const checkboxes = document.querySelectorAll('[name^="marcou_gol_"]');
            checkboxes.forEach(function(checkbox) {
                const playerId = checkbox.id.replace('marcou_gol_', '');
                const golsGroup = document.getElementById('gols_group_' + playerId);
                
                checkbox.addEventListener('change', function() {
                    golsGroup.style.display = this.checked ? 'block' : 'none';
                    if (this.checked) {
                        golsGroup.querySelector('input').value = '1';
                    }
                });
            });
        });
    </script>
    """

    return render_template_string(BASE_HTML, content=content)

@app.route('/resumo-jogo/<int:jogo_id>', methods=['GET','POST'])
def resumo_jogo(jogo_id):
    jogo = Jogo.query.get_or_404(jogo_id)
    # APENAS quem confirmou presença aparece no resumo técnico
    presentes = Participacao.query.filter_by(jogo_id=jogo_id, confirmou=True).all()

    if request.method == 'POST':
        jogo.resumo_texto = request.form.get('resumo')
        jogo.craque_id = request.form.get('craque_id') or None
        
        for p in presentes:
            # Verifica se o jogador marcou gol
            if f'marcou_gol_{p.id}' in request.form:
                p.gols = int(request.form.get(f'gols_{p.id}') or 1)
            else:
                p.gols = 0
            
            p.expulso = f'expulso_{p.id}' in request.form
        
        db.session.commit()
        return redirect(url_for('jogos'))

    content = f"""
    <h4>📝 Resumo Técnico: {jogo.adversario}</h4>
    <p class="text-muted">
    {jogo.adversario} — {jogo.data.strftime('%d/%m/%Y')}
    </p>

    <form method='post'>
        <div class='card p-3 mb-4 shadow-sm'>
            <h5 class='mb-3'>⚽ Quem fez gol?</h5>
            <div class='row'>
    """

    for p in presentes:
        content += f"""
                <div class='col-md-4 mb-3'>
                    <div class='card border-secondary'>
                        <div class='card-body text-center'>
                            <div class='form-check mb-2'>
                                <input class='form-check-input' type='checkbox' name='marcou_gol_{p.id}' id='marcou_gol_{p.id}' {'checked' if p.gols > 0 else ''}>
                                <label class='form-check-label' for='marcou_gol_{p.id}'>
                                    <strong>{p.jogador.nome}</strong>
                                </label>
                            </div>
                            <div class='form-group' id='gols_group_{p.id}' style='display: {'block' if p.gols > 0 else 'none'}'>
                                <label class='form-label small'>Quantos gols?</label>
                                <input type='number'
                                       min='1'
                                       name='gols_{p.id}'
                                       value='{p.gols if p.gols > 0 else 1}'
                                       class='form-control form-control-sm text-center'
                                       placeholder='1'>
                            </div>
                        </div>
                    </div>
                </div>
        """

    content += f"""
            </div>
        </div>

        <div class='card p-3 mb-4 shadow-sm'>
            <h5 class='mb-3'>🟥 Expulsões</h5>
            <div class='row'>
    """

    for p in presentes:
        content += f"""
                <div class='col-md-4 mb-3'>
                    <div class='form-check form-check-card'>
                        <input class='form-check-input' type='checkbox' name='expulso_{p.id}' id='expulso_{p.id}' {'checked' if p.expulso else ''}>
                        <label class='form-check-label d-block p-3 border rounded text-center' for='expulso_{p.id}'>
                            <strong>{p.jogador.nome}</strong>
                            <div class='text-danger small'>🟥 Expulso</div>
                        </label>
                    </div>
                </div>
        """

    content += f"""
            </div>
        </div>

        <div class="card p-3 shadow-sm mb-3">
            <label class="form-label">⭐ Craque da Partida</label>
            <select name="craque_id" class="form-select">
                <option value="">Nenhum</option>
                {''.join([
                    f"<option value='{p.jogador_id}' {'selected' if jogo.craque_id == p.jogador_id else ''}>{p.jogador.nome}</option>"
                    for p in presentes
                ])}
            </select>

            <label class="form-label mt-3">📝 Resumo da Partida</label>
            <textarea name="resumo" rows="4" class="form-control">{jogo.resumo_texto or ''}</textarea>

            <button class="btn btn-success mt-3 w-100">Salvar Resumo</button>
        </div>

    </form>
    
    <script>
        // Mostrar/ocultar campo de gols quando checkbox é marcado
        document.addEventListener('DOMContentLoaded', function() {
            const checkboxes = document.querySelectorAll('[name^="marcou_gol_"]');
            checkboxes.forEach(function(checkbox) {
                const playerId = checkbox.id.replace('marcou_gol_', '');
                const golsGroup = document.getElementById('gols_group_' + playerId);
                
                checkbox.addEventListener('change', function() {
                    golsGroup.style.display = this.checked ? 'block' : 'none';
                    if (this.checked) {
                        golsGroup.querySelector('input').value = '1';
                    }
                });
            });
        });
    </script>
    """

    return render_template_string(BASE_HTML, content=content)


@app.route('/jogadores', methods=['GET','POST'])
def jogadores():
    if request.method == 'POST':
        db.session.add(Jogador(nome=request.form['nome'], telefone=request.form['telefone'], tipo=request.form['tipo']))
        db.session.commit()
        return redirect('/jogadores')
    
    j_list = Jogador.query.all()
    rows = "".join([f"<tr><td>{j.nome}</td><td>{j.telefone}</td><td>{j.tipo}</td></tr>" for j in j_list])
    content = f"""
    <h3>👥 Atletas</h3>
    <form method='post' class='row g-2 mb-4 card p-3 shadow-sm flex-row'>
        <div class='col-md-4'><input name='nome' placeholder='Nome Completo' class='form-control' required></div>
        <div class='col-md-3'><input name='telefone' placeholder='WhatsApp' class='form-control'></div>
        <div class='col-md-3'><select name='tipo' class='form-select'><option value='SOCIO'>Sócio</option><option value='CONVIDADO'>Convidado</option></select></div>
        <div class='col-md-2'><button class='btn btn-primary w-100'>Cadastrar</button></div>
    </form>
    <table class='table bg-white shadow-sm'><thead><tr><th>Nome</th><th>Telefone</th><th>Tipo</th></tr></thead><tbody>{rows}</tbody></table>
    """
    return render_template_string(BASE_HTML, content=content)


@app.route('/associados', methods=['GET','POST'])
def associados():
    # Simplificado para foco na sua nova lógica de jogos
    socios = Jogador.query.filter_by(tipo='SOCIO').all()
    if request.method == 'POST':
        db.session.add(Financeiro(
            data=date.today(), tipo='MENSALIDADE', 
            descricao=f"Mensalidade {request.form['mes']} - {request.form['nome']}", 
            valor=float(request.form['valor'])
        ))
        db.session.commit()
    
    content = "<h3>💰 Controle de Mensalidades</h3><p>Use o formulário para lançar pagamentos fixos mensais.</p>"
    # Adicionar form aqui conforme necessário...
    return render_template_string(BASE_HTML, content=content + "<a href='/' class='btn btn-secondary'>Voltar</a>")

@app.route('/financeiro')
def financeiro():
    movs = Financeiro.query.order_by(Financeiro.data.desc()).all()
    rows = "".join([f"<tr><td>{m.data}</td><td>{m.tipo}</td><td>{m.descricao}</td><td>R$ {m.valor:.2f}</td></tr>" for m in movs])
    return render_template_string(BASE_HTML, content=f"<h3>📊 Extrato de Caixa</h3><table class='table bg-white'><thead><tr><th>Data</th><th>Tipo</th><th>Descrição</th><th>Valor</th></tr></thead><tbody>{rows}</tbody></table>")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)