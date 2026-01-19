"""
Sistema de Gestão de Associação Esportiva
Flask + SQLAlchemy + Bootstrap
"""

from flask import Flask, request, redirect, url_for, render_template, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
import logging
import os
from functools import wraps

# ================= CONFIGURAÇÃO =================
app = Flask(__name__)
# Configuração simples - pode ser melhorada com config.py no futuro
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///associacao.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)

# ================= MODELOS =================

class Jogador(db.Model):
    """Modelo para jogadores (sócios e convidados)"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, index=True)
    telefone = db.Column(db.String(20))
    tipo = db.Column(db.String(10), nullable=False, index=True)  # SOCIO / CONVIDADO
    
    def __repr__(self):
        return f'<Jogador {self.nome}>'

class Jogo(db.Model):
    """Modelo para jogos"""
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, index=True)
    adversario = db.Column(db.String(100))
    local = db.Column(db.String(100))
    valor_jogo = db.Column(db.Float, default=0)
    resumo_texto = db.Column(db.Text)
    craque_id = db.Column(db.Integer, db.ForeignKey('jogador.id'))
    
    # Relacionamentos
    participantes = db.relationship('Participacao', backref='jogo', cascade="all, delete-orphan")
    craque = db.relationship('Jogador', foreign_keys=[craque_id])
    
    def __repr__(self):
        return f'<Jogo {self.data} vs {self.adversario}>'

class Participacao(db.Model):
    """Tabela central que une Jogador, Jogo, Financeiro e Estatísticas"""
    id = db.Column(db.Integer, primary_key=True)
    jogo_id = db.Column(db.Integer, db.ForeignKey('jogo.id'), nullable=False, index=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=False, index=True)
    
    # Presença e Financeiro
    confirmou = db.Column(db.Boolean, default=False)
    pagou = db.Column(db.Boolean, default=False)
    valor_pago = db.Column(db.Float, default=0)
    lancado_financeiro = db.Column(db.Boolean, default=False)  # Evita duplicar no financeiro

    # Estatísticas
    gols = db.Column(db.Integer, default=0)
    expulso = db.Column(db.Boolean, default=False)

    jogador = db.relationship('Jogador')
    
    # Índice único para evitar duplicatas
    __table_args__ = (db.UniqueConstraint('jogo_id', 'jogador_id', name='unique_participacao'),)
    
    def __repr__(self):
        return f'<Participacao {self.jogador.nome} no jogo {self.jogo_id}>'

class Financeiro(db.Model):
    """Modelo para movimentações financeiras"""
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, index=True)
    tipo = db.Column(db.String(15), nullable=False, index=True)  # MENSALIDADE / PARTIDA / DESPESA
    descricao = db.Column(db.String(200))
    valor = db.Column(db.Float, nullable=False)
    # Campos adicionais para mensalidades
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=True, index=True)
    mes_referencia = db.Column(db.String(20))  # Ex: "01/2024" ou "Janeiro/2024"
    ano_referencia = db.Column(db.Integer)  # Ano da mensalidade
    
    jogador = db.relationship('Jogador', foreign_keys=[jogador_id])
    
    def __repr__(self):
        return f'<Financeiro {self.tipo} - R$ {self.valor}>'

# ================= VALIDAÇÕES E UTILITÁRIOS =================

def validar_valor(valor_str):
    """Valida e converte valor monetário"""
    try:
        valor = float(valor_str)
        if valor < 0:
            raise ValueError("Valor não pode ser negativo")
        return valor
    except (ValueError, TypeError):
        raise ValueError("Valor inválido")

def validar_data(data_str):
    """Valida formato de data"""
    try:
        return date.fromisoformat(data_str)
    except (ValueError, TypeError):
        raise ValueError("Data inválida")

def validar_tipo_jogador(tipo):
    """Valida tipo de jogador"""
    tipos_validos = ['SOCIO', 'CONVIDADO']
    if tipo not in tipos_validos:
        raise ValueError(f"Tipo inválido. Use: {', '.join(tipos_validos)}")
    return tipo

# ================= ROTAS =================

@app.route('/')
def index():
    """Dashboard principal com resumo financeiro"""
    try:
        mensal = db.session.query(db.func.sum(Financeiro.valor)).filter(
            Financeiro.tipo == 'MENSALIDADE'
        ).scalar() or 0
        
        partidas = db.session.query(db.func.sum(Financeiro.valor)).filter(
            Financeiro.tipo == 'PARTIDA'
        ).scalar() or 0
        
        despesas = db.session.query(db.func.sum(Financeiro.valor)).filter(
            Financeiro.tipo == 'DESPESA'
        ).scalar() or 0
        
        saldo = mensal + partidas - despesas
        
        return render_template('index.html', 
                             saldo=saldo, 
                             mensal=mensal, 
                             partidas=partidas, 
                             despesas=despesas)
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        flash('Erro ao carregar dados do dashboard', 'danger')
        return render_template('index.html', saldo=0, mensal=0, partidas=0, despesas=0)

@app.route('/jogos', methods=['GET', 'POST'])
def jogos():
    """Lista e cria jogos"""
    if request.method == 'POST':
        try:
            # Validações
            data_jogo = validar_data(request.form['data'])
            adversario = request.form.get('adversario', '').strip()
            if not adversario:
                flash('Adversário é obrigatório', 'danger')
                return redirect(url_for('jogos'))
            
            valor_jogo = validar_valor(request.form.get('valor_jogo') or 0)
            local = request.form.get('local', '').strip()
            
            # Criar jogo
            novo_jogo = Jogo(
                data=data_jogo,
                adversario=adversario,
                local=local,
                valor_jogo=valor_jogo
            )
            db.session.add(novo_jogo)
            db.session.flush()  # Gera ID do jogo antes do commit final

            # Criar participações vazias para todos os jogadores ativos
            jogadores = Jogador.query.all()
            if not jogadores:
                flash('Cadastre pelo menos um jogador antes de criar um jogo', 'warning')
                db.session.rollback()
                return redirect(url_for('jogos'))
            
            for j in jogadores:
                # Verificar se já existe participação
                participacao_existente = Participacao.query.filter_by(
                    jogo_id=novo_jogo.id, 
                    jogador_id=j.id
                ).first()
                
                if not participacao_existente:
                    db.session.add(Participacao(jogo_id=novo_jogo.id, jogador_id=j.id))
            
            db.session.commit()
            flash('Jogo cadastrado com sucesso!', 'success')
            logger.info(f"Jogo criado: {novo_jogo}")
            return redirect(url_for('jogos'))
            
        except ValueError as e:
            db.session.rollback()
            flash(f'Erro de validação: {str(e)}', 'danger')
            logger.warning(f"Erro de validação ao criar jogo: {e}")
        except Exception as e:
            db.session.rollback()
            flash('Erro ao cadastrar jogo', 'danger')
            logger.error(f"Erro ao criar jogo: {e}")

    # GET - Listar jogos
    try:
        lista_jogos = Jogo.query.order_by(Jogo.data.desc()).all()
        return render_template('jogos.html', jogos=lista_jogos)
    except Exception as e:
        logger.error(f"Erro ao listar jogos: {e}")
        flash('Erro ao carregar lista de jogos', 'danger')
        return render_template('jogos.html', jogos=[])

@app.route('/presencas/<int:jogo_id>', methods=['GET', 'POST'])
def presencas(jogo_id):
    """Gerencia presenças e pagamentos de um jogo"""
    jogo = Jogo.query.get_or_404(jogo_id)
    participacoes = Participacao.query.filter_by(jogo_id=jogo_id).all()

    if request.method == 'POST':
        try:
            for p in participacoes:
                p.confirmou = f'confirmou_{p.id}' in request.form
                p.pagou = f'pagou_{p.id}' in request.form
                
                # Validar valor pago
                valor_str = request.form.get(f'valor_{p.id}') or '0'
                try:
                    p.valor_pago = validar_valor(valor_str)
                except ValueError:
                    p.valor_pago = 0

                # Lógica Financeira: Só lança se pagou e ainda não foi lançado
                if p.pagou and p.valor_pago > 0 and not p.lancado_financeiro:
                    db.session.add(Financeiro(
                        data=date.today(),
                        tipo='PARTIDA',
                        descricao=f"Pgto Jogo {jogo.data.strftime('%d/%m/%Y')} - {p.jogador.nome}",
                        valor=p.valor_pago
                    ))
                    p.lancado_financeiro = True
            
            # Adicionar Despesa do Jogo
            desc_despesa = request.form.get('desc_despesa', '').strip()
            val_despesa = request.form.get('val_despesa')
            
            if desc_despesa and val_despesa:
                try:
                    valor_despesa = validar_valor(val_despesa)
                    db.session.add(Financeiro(
                        data=date.today(),
                        tipo='DESPESA',
                        descricao=f"Despesa Jogo {jogo.data.strftime('%d/%m/%Y')}: {desc_despesa}",
                        valor=valor_despesa
                    ))
                except ValueError as e:
                    flash(f'Erro ao adicionar despesa: {str(e)}', 'warning')

            db.session.commit()
            flash('Presenças e pagamentos atualizados!', 'success')
            logger.info(f"Presenças atualizadas para jogo {jogo_id}")
            return redirect(url_for('presencas', jogo_id=jogo_id))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao salvar alterações', 'danger')
            logger.error(f"Erro ao salvar presenças: {e}")

    # Calcular totais
    total_arrecadado = sum(p.valor_pago for p in participacoes if p.pagou)
    
    return render_template('presencas.html', 
                         jogo=jogo, 
                         participacoes=participacoes,
                         total_arrecadado=total_arrecadado)

@app.route('/resumo-jogo/<int:jogo_id>', methods=['GET', 'POST'])
def resumo_jogo(jogo_id):
    """Resumo técnico do jogo (gols, expulsões, craque)"""
    jogo = Jogo.query.get_or_404(jogo_id)
    # APENAS quem confirmou presença aparece no resumo técnico
    presentes = Participacao.query.filter_by(jogo_id=jogo_id, confirmou=True).all()

    if request.method == 'POST':
        try:
            jogo.resumo_texto = request.form.get('resumo', '').strip()
            craque_id = request.form.get('craque_id')
            jogo.craque_id = int(craque_id) if craque_id and craque_id.isdigit() else None
            
            for p in presentes:
                # Verifica se o jogador marcou gol
                if f'marcou_gol_{p.id}' in request.form:
                    gols_str = request.form.get(f'gols_{p.id}') or '1'
                    try:
                        p.gols = max(0, int(gols_str))  # Garantir não negativo
                    except ValueError:
                        p.gols = 1
                else:
                    p.gols = 0
                
                p.expulso = f'expulso_{p.id}' in request.form
            
            db.session.commit()
            flash('Resumo técnico salvo com sucesso!', 'success')
            logger.info(f"Resumo técnico atualizado para jogo {jogo_id}")
            return redirect(url_for('jogos'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao salvar resumo técnico', 'danger')
            logger.error(f"Erro ao salvar resumo: {e}")

    return render_template('resumo_jogo.html', jogo=jogo, presentes=presentes)

@app.route('/jogadores', methods=['GET', 'POST'])
def jogadores():
    """Lista e cadastra jogadores"""
    if request.method == 'POST':
        try:
            nome = request.form['nome'].strip()
            if not nome:
                flash('Nome é obrigatório', 'danger')
                return redirect(url_for('jogadores'))
            
            telefone = request.form.get('telefone', '').strip()
            tipo = validar_tipo_jogador(request.form['tipo'])
            
            # Verificar se já existe jogador com mesmo nome
            jogador_existente = Jogador.query.filter_by(nome=nome).first()
            if jogador_existente:
                flash(f'Jogador "{nome}" já está cadastrado', 'warning')
                return redirect(url_for('jogadores'))
            
            novo_jogador = Jogador(nome=nome, telefone=telefone, tipo=tipo)
            db.session.add(novo_jogador)
            db.session.commit()
            flash(f'Jogador "{nome}" cadastrado com sucesso!', 'success')
            logger.info(f"Jogador criado: {novo_jogador}")
            return redirect(url_for('jogadores'))
            
        except ValueError as e:
            db.session.rollback()
            flash(f'Erro de validação: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Erro ao cadastrar jogador', 'danger')
            logger.error(f"Erro ao criar jogador: {e}")
    
    try:
        jogadores_list = Jogador.query.order_by(Jogador.nome).all()
        return render_template('jogadores.html', jogadores=jogadores_list)
    except Exception as e:
        logger.error(f"Erro ao listar jogadores: {e}")
        flash('Erro ao carregar lista de jogadores', 'danger')
        return render_template('jogadores.html', jogadores=[])

@app.route('/associados', methods=['GET', 'POST'])
def associados():
    """Controle de mensalidades"""
    socios = Jogador.query.filter_by(tipo='SOCIO').order_by(Jogador.nome).all()
    
    if request.method == 'POST':
        try:
            mes = request.form.get('mes', '').strip()
            ano = request.form.get('ano', '').strip()
            jogador_id = request.form.get('jogador_id')
            valor_str = request.form.get('valor')
            
            if not mes or not ano or not jogador_id or not valor_str:
                flash('Preencha todos os campos obrigatórios', 'danger')
                return redirect(url_for('associados'))
            
            # Validar ano
            try:
                ano_int = int(ano)
                if ano_int < 2000 or ano_int > 2100:
                    raise ValueError("Ano inválido")
            except ValueError:
                flash('Ano inválido', 'danger')
                return redirect(url_for('associados'))
            
            valor = validar_valor(valor_str)
            jogador = Jogador.query.get(int(jogador_id))
            
            if not jogador:
                flash('Jogador não encontrado', 'danger')
                return redirect(url_for('associados'))
            
            # Verificar se já existe mensalidade para este mês/ano/jogador
            mes_ano = f"{mes}/{ano}"
            mensalidade_existente = Financeiro.query.filter_by(
                tipo='MENSALIDADE',
                jogador_id=jogador.id,
                mes_referencia=mes_ano,
                ano_referencia=ano_int
            ).first()
            
            if mensalidade_existente:
                flash(f'Mensalidade de {mes}/{ano} para {jogador.nome} já está cadastrada', 'warning')
                return redirect(url_for('associados'))
            
            # Criar mensalidade
            db.session.add(Financeiro(
                data=date.today(),
                tipo='MENSALIDADE',
                descricao=f"Mensalidade {mes}/{ano} - {jogador.nome}",
                valor=valor,
                jogador_id=jogador.id,
                mes_referencia=mes_ano,
                ano_referencia=ano_int
            ))
            db.session.commit()
            flash(f'Mensalidade de {mes}/{ano} para {jogador.nome} lançada com sucesso!', 'success')
            logger.info(f"Mensalidade lançada: {mes}/{ano} - {jogador.nome} - R$ {valor}")
            return redirect(url_for('associados'))
            
        except ValueError as e:
            db.session.rollback()
            flash(f'Erro de validação: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Erro ao lançar mensalidade', 'danger')
            logger.error(f"Erro ao lançar mensalidade: {e}")
    
    # Buscar todas as mensalidades agrupadas por sócio
    mensalidades_por_socio = {}
    for socio in socios:
        mensalidades = Financeiro.query.filter_by(
            tipo='MENSALIDADE',
            jogador_id=socio.id
        ).order_by(Financeiro.ano_referencia.desc(), Financeiro.mes_referencia.desc()).all()
        
        mensalidades_por_socio[socio.id] = {
            'socio': socio,
            'mensalidades': mensalidades,
            'total_pago': sum(m.valor for m in mensalidades)
        }
    
    # Obter anos únicos para o filtro
    anos = sorted(set(
        m.ano_referencia for m in Financeiro.query.filter_by(tipo='MENSALIDADE')
        .filter(Financeiro.ano_referencia.isnot(None)).all()
    ), reverse=True)
    
    # Calcular total geral
    total_geral = sum(dados['total_pago'] for dados in mensalidades_por_socio.values())
    
    return render_template('associados.html', 
                         socios=socios,
                         mensalidades_por_socio=mensalidades_por_socio,
                         anos=anos,
                         total_geral=total_geral)

@app.route('/financeiro')
def financeiro():
    """Extrato financeiro"""
    try:
        movs = Financeiro.query.order_by(Financeiro.data.desc(), Financeiro.id.desc()).all()
        
        # Calcular saldo acumulado
        saldo_atual = 0
        movimentacoes = []
        for m in movs:
            if m.tipo == 'DESPESA':
                saldo_atual -= m.valor
            else:
                saldo_atual += m.valor
            movimentacoes.append({
                'mov': m,
                'saldo_acumulado': saldo_atual
            })
        
        return render_template('financeiro.html', movimentacoes=movimentacoes)
    except Exception as e:
        logger.error(f"Erro ao carregar financeiro: {e}")
        flash('Erro ao carregar extrato financeiro', 'danger')
        return render_template('financeiro.html', movimentacoes=[])

# ================= HANDLERS DE ERRO =================

@app.errorhandler(404)
def not_found(error):
    flash('Página não encontrada', 'warning')
    return redirect(url_for('index')), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Erro interno: {error}")
    flash('Erro interno do servidor', 'danger')
    return redirect(url_for('index')), 500

@app.route('/extornar-mensalidade/<int:mensalidade_id>', methods=['POST'])
def extornar_mensalidade(mensalidade_id):
    """Extorna (remove) uma mensalidade"""
    try:
        mensalidade = Financeiro.query.get_or_404(mensalidade_id)
        
        if mensalidade.tipo != 'MENSALIDADE':
            flash('Esta movimentação não é uma mensalidade', 'danger')
            return redirect(url_for('associados'))
        
        jogador_nome = mensalidade.jogador.nome if mensalidade.jogador else 'Desconhecido'
        mes_ano = mensalidade.mes_referencia or 'N/A'
        
        db.session.delete(mensalidade)
        db.session.commit()
        
        flash(f'Mensalidade de {mes_ano} para {jogador_nome} foi extornada com sucesso!', 'success')
        logger.info(f"Mensalidade extornada: ID {mensalidade_id} - {mes_ano} - {jogador_nome}")
        return redirect(url_for('associados'))
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao extornar mensalidade', 'danger')
        logger.error(f"Erro ao extornar mensalidade: {e}")
        return redirect(url_for('associados'))

# ================= INICIALIZAÇÃO =================

if __name__ == '__main__':
    with app.app_context():
        # Criar todas as tabelas se não existirem
        db.create_all()
        
        # Verificar e adicionar colunas faltantes no modelo Financeiro (migração)
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('financeiro')]
            
            if 'jogador_id' not in columns:
                logger.info("Adicionando coluna jogador_id ao banco de dados...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN jogador_id INTEGER'))
                db.session.commit()
            
            if 'mes_referencia' not in columns:
                logger.info("Adicionando coluna mes_referencia ao banco de dados...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN mes_referencia VARCHAR(20)'))
                db.session.commit()
            
            if 'ano_referencia' not in columns:
                logger.info("Adicionando coluna ano_referencia ao banco de dados...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN ano_referencia INTEGER'))
                db.session.commit()
        except Exception as e:
            logger.warning(f"Aviso ao verificar colunas: {e}")
        
        logger.info("Banco de dados inicializado")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
