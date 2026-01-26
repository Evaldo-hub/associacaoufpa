"""
Sistema de Gestão de Associação Esportiva
Flask + SQLAlchemy + Bootstrap
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, date, time
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import os
from functools import wraps
from urllib.parse import quote
from flask import jsonify
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

# ================= CONFIGURAÇÃO =================
app = Flask(__name__, static_folder='static')

app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY',
    'dev-secret-key-change-in-production'
)

# ================= ROTAS PWA =================
@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")

# ================= BANCO DE DADOS =================
db_url = os.environ.get("DATABASE_URL")

# Permite rodar local com SQLite
if not db_url:
    db_url = "sqlite:///local.db"
    print("DATABASE_URL nao encontrada. Usando SQLite local.")

# Corrige padrão antigo do Render
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)

# ================= LOGIN =================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None


# ================= MODELOS =================

class User(UserMixin, db.Model):
    __tablename__ = "user"  # explícito (boa prática)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='visualizador')
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    jogador = db.relationship(
        'Jogador',
        backref=db.backref('user', uselist=False),
        foreign_keys=[jogador_id]
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.username}>'



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Jogador(db.Model):
    """Modelo para jogadores (sócios e convidados)"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, index=True)
    telefone = db.Column(db.String(20))
    tipo = db.Column(db.String(10), nullable=False, index=True)  # SOCIO / CONVIDADO
    ativo = db.Column(db.Boolean, default=True, nullable=False)  # Status do jogador
    nativo = db.Column(db.Boolean, default=False, nullable=False)  # Se é nativo
    
    def __repr__(self):
        return f'<Jogador {self.nome}>'

class Jogo(db.Model):
    """Modelo para jogos"""
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, index=True)
    horario = db.Column(db.Time, nullable=False, default=time(19, 0))  # 19:00 por padrão
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

class Auditoria(db.Model):
    """Modelo para auditoria de extornos e alterações importantes"""
    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    acao = db.Column(db.String(50), nullable=False, index=True)  # EXTORNO_DESPESA, EXTORNO_MOVIMENTACAO, etc.
    tabela_afetada = db.Column(db.String(50), nullable=False)  # financeiro, mensalidades, etc.
    registro_id = db.Column(db.Integer, nullable=False)  # ID do registro original
    motivo = db.Column(db.Text, nullable=False)  # Motivo do extorno
    dados_originais = db.Column(db.Text)  # JSON com dados originais
    usuario = db.Column(db.String(100))  # Usuário que realizou a ação (futuro)
    
    def __repr__(self):
        return f'<Auditoria {self.acao} - {self.data_hora}>'

# ================= INICIALIZAÇÃO DO BANCO =================
with app.app_context():
    try:
        db.create_all()

        # Cria admin padrão se não existir
        if not User.query.filter_by(username="admin").first():
            admin = User(
                username="admin",
                email="admin@admin.com",
                role="admin"
            )
            admin.set_password("@admin1974")
            db.session.add(admin)
            db.session.commit()
            logger.info("Usuario admin criado com sucesso")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro na inicialização do banco: {e}")

# ================= VALIDAÇÕES E UTILITÁRIOS =================

def forcar_refresh_banco():
    """Força o SQLAlchemy a buscar dados atualizados do banco"""
    try:
        db.session.expire_all()
        # Remove flush() para evitar problemas de transação
        logger.info("Refresh do banco forçado com sucesso")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao forçar refresh do banco: {e}")

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

@app.route('/pwa/')
def pwa_entry():
    return redirect('/login/')


@app.route("/login/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        logger.info(f"Usuário já autenticado: {current_user.username}")
        return redirect('/')

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        logger.info(f"Tentativa de login para usuário: {username}")

        try:
            user = User.query.filter_by(username=username).first()

            if user and user.check_password(password):
                login_user(user)
                logger.info(f"Login bem-sucedido para: {username}")
                next_page = request.args.get("next")
                redirect_url = next_page or '/'
                logger.info(f"Redirecionando para: {redirect_url}")
                return redirect(redirect_url)

            logger.warning(f"Credenciais inválidas para usuário: {username}")
            flash("Usuário ou senha inválidos", "danger")
        except Exception as e:
            logger.error(f"Erro no login: {e}")
            flash("Erro ao processar login. Tente novamente.", "danger")

    return render_template("login.html")


@app.route('/logout/')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema com sucesso!', 'info')
    return redirect('/login/')


@app.route('/')
@login_required
def index():
    """Dashboard principal com resumo financeiro, artilharia e próximo jogo"""
    logger.info(f"Acessando dashboard - Usuário: {current_user.username}")
    
    try:
        # Forçar refresh do banco para garantir dados atualizados
        forcar_refresh_banco()
        
        # Buscar dados atualizados financeiros
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
        
        # Próximo jogo
        proximo_jogo = Jogo.query.filter(
            Jogo.data >= date.today()
        ).order_by(Jogo.data.asc()).first()
        
        # Calcular dias até o próximo jogo
        if proximo_jogo:
            dias_proximo_jogo = (proximo_jogo.data - date.today()).days
        else:
            dias_proximo_jogo = None
        
        # Dados da artilharia
        artilharia = []
        jogadores = Jogador.query.all()
        
        for jogador in jogadores:
            total_gols = db.session.query(db.func.sum(Participacao.gols)).filter(
                Participacao.jogador_id == jogador.id
            ).scalar() or 0
            
            if total_gols > 0:
                artilharia.append({
                    'nome': jogador.nome,
                    'gols': total_gols
                })
        
        # Ordenar por quantidade de gols (maior para menor)
        artilharia.sort(key=lambda x: x['gols'], reverse=True)
        
        # Pegar apenas os top 10 para o gráfico
        top_artilheiros = artilharia[:10]
        
        logger.info(f"Dashboard carregado com sucesso para {current_user.username}")
        return render_template('index.html', 
                             saldo=saldo, 
                             mensal=mensal, 
                             partidas=partidas, 
                             despesas=despesas,
                             artilharia=top_artilheiros,
                             proximo_jogo=proximo_jogo,
                             dias_proximo_jogo=dias_proximo_jogo)
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        flash('Erro ao carregar dados do dashboard', 'danger')
        return render_template('index.html', 
                             saldo=0, 
                             mensal=0, 
                             partidas=0, 
                             despesas=0,
                             artilharia=[],
                             proximo_jogo=None)

@app.route('/jogos', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/jogos/', methods=['GET', 'POST'], strict_slashes=False)
@login_required
def jogos():
    """Lista e cria jogos"""
    try:
        # Forçar refresh do banco para garantir dados atualizados
        forcar_refresh_banco()
        
        if request.method == 'POST':
            # Verificar permissão - apenas admins podem criar jogos
            if not current_user.is_admin():
                flash('Apenas administradores podem criar jogos', 'danger')
                return redirect(url_for('jogos'))
            
            try:
                # Validações
                data_jogo = validar_data(request.form['data'])
                horario_str = request.form.get('horario', '19:00')
                adversario = request.form.get('adversario', '').strip()
                if not adversario:
                    raise ValueError("Adversário é obrigatório")
                
                # Converter horário
                from datetime import datetime
                try:
                    horario = datetime.strptime(horario_str, '%H:%M').time()
                except ValueError:
                    horario = time(19, 0)  # Padrão 19:00
                
                # Criar jogo
                novo_jogo = Jogo(
                    data=data_jogo,
                    horario=horario,
                    adversario=adversario,
                    local=request.form.get('local', '')
                )
                
                db.session.add(novo_jogo)
                db.session.commit()
                flash('Jogo criado com sucesso!', 'success')
                return redirect(url_for('jogos'))
                
            except ValueError as e:
                flash(f'Erro de validação: {str(e)}', 'danger')
                logger.warning(f"Erro de validação ao criar jogo: {e}")
            except Exception as e:
                db.session.rollback()
                flash('Erro ao cadastrar jogo', 'danger')
                logger.error(f"Erro ao criar jogo: {e}")
        
        # GET - Listar jogos
        lista_jogos = Jogo.query.order_by(Jogo.data.desc()).all()
        return render_template('jogos.html', 
                             jogos=lista_jogos,
                             data_atual=date.today().isoformat(),
                             adversario_padrao="",
                             local_padrao="Campo da UFPA")
        
    except Exception as e:
        logger.error(f"Erro ao carregar jogos: {e}")
        flash('Erro ao carregar lista de jogos', 'danger')
        return render_template('jogos.html', jogos=[])

@app.route('/presencas/<int:jogo_id>', methods=['GET', 'POST'])
@login_required
def presencas(jogo_id):
    """Gerencia presenças e pagamentos de um jogo"""
    try:
        # Forçar refresh do banco para garantir dados atualizados
        forcar_refresh_banco()
        
        jogo = Jogo.query.get_or_404(jogo_id)
        participacoes = Participacao.query.filter_by(jogo_id=jogo_id).all()

        if request.method == 'POST':
            try:
                # Verificar se é para adicionar novo jogador (admin ou próprio sócio)
                if request.form.get('acao') == 'add_jogador':
                    novo_jogador_id = request.form.get('novo_jogador_id')
                    
                    # Se não for admin, só pode adicionar a si mesmo
                    if not current_user.is_admin():
                        if not current_user.jogador_id:
                            flash('Você não está associado a nenhum jogador', 'danger')
                            return redirect(url_for('presencas', jogo_id=jogo_id))
                        
                        # Sócio só pode se adicionar ao jogo
                        novo_jogador_id = current_user.jogador_id
                    
                    if novo_jogador_id:
                        # Verificar se jogador já não está no jogo
                        participacao_existente = Participacao.query.filter_by(
                            jogo_id=jogo_id, 
                            jogador_id=int(novo_jogador_id)
                        ).first()
                        
                        if participacao_existente:
                            if current_user.is_admin():
                                flash('Este jogador já está adicionado ao jogo', 'warning')
                            else:
                                flash('Você já está adicionado a este jogo', 'warning')
                        else:
                            # Verificar se o jogador é sócio para adicionar a si mesmo
                            if not current_user.is_admin():
                                jogador = Jogador.query.get(current_user.jogador_id)
                                if jogador.tipo != 'SOCIO':
                                    flash('Apenas sócios podem se adicionar aos jogos', 'danger')
                                else:
                                    # Adicionar sócio ao jogo
                                    nova_participacao = Participacao(
                                        jogo_id=jogo_id,
                                        jogador_id=current_user.jogador_id
                                    )
                                    db.session.add(nova_participacao)
                                    db.session.commit()
                                    flash('Você foi adicionado ao jogo com sucesso!', 'success')
                            else:
                                # Admin adiciona qualquer jogador
                                nova_participacao = Participacao(
                                    jogo_id=jogo_id,
                                    jogador_id=int(novo_jogador_id)
                                )
                                db.session.add(nova_participacao)
                                db.session.commit()
                                flash('Jogador adicionado ao jogo com sucesso!', 'success')
                    else:
                        if current_user.is_admin():
                            flash('Selecione um jogador para adicionar', 'warning')
                        else:
                            flash('Erro ao tentar se adicionar ao jogo', 'danger')
                    
                    return redirect(url_for('presencas', jogo_id=jogo_id))
                
                # Lógica para atualizar presenças com verificação de permissões
                for p in participacoes:
                    # Se não for admin, só permitir editar própria confirmação
                    if not current_user.is_admin():
                        # Verificar se é o próprio jogador
                        if current_user.jogador_id != p.jogador_id:
                            continue  # Pular outros jogadores
                        
                        # Jogadores só podem confirmar própria presença
                        if f'confirmou_{p.id}' in request.form:
                            p.confirmou = True
                            flash('Sua presença foi confirmada!', 'success')
                            logger.info(f"Jogador {current_user.jogador_id} confirmou presença no jogo {jogo_id}")
                        
                        # Não permitir editar outros campos
                        continue
                    
                    # Admin pode editar todos os campos
                    p.confirmou = f'confirmou_{p.id}' in request.form
                    p.pagou = f'pagou_{p.id}' in request.form
                    
                    # Validar valor pago
                    valor_str = request.form.get(f'valor_{p.id}') or '0'
                    try:
                        p.valor_pago = validar_valor(valor_str)
                    except ValueError:
                        p.valor_pago = 0

                    # Atualizar dados técnicos (gols, expulsões)
                    gols_str = request.form.get(f'gols_{p.id}') or '0'
                    try:
                        p.gols = max(0, int(gols_str))
                    except ValueError:
                        p.gols = 0
                    
                    p.expulso = f'expulso_{p.id}' in request.form

                    # Lógica Financeira: Só lança se pagou e ainda não foi lançado
                    if p.pagou and p.valor_pago > 0 and not p.lancado_financeiro:
                        db.session.add(Financeiro(
                            data=date.today(),
                            tipo='PARTIDA',
                            descricao=f"Pgto Jogo {jogo.data.strftime('%d/%m/%Y')} - {p.jogador.nome}",
                            valor=p.valor_pago
                        ))
                        p.lancado_financeiro = True
                
                # Atualizar craque da partida
                craque_id = request.form.get('craque_id')
                jogo.craque_id = int(craque_id) if craque_id and craque_id.isdigit() else None
                
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
        total_despesas = 0  # Inicia sem valor do campo
        total_confirmados = sum(1 for p in participacoes if p.confirmou)
        
        # Buscar despesas da partida
        data_jogo = jogo.data.strftime('%d/%m/%Y')
        despesas_partida = Financeiro.query.filter(
            Financeiro.descricao.like(f"Despesa Jogo {data_jogo}%")
        ).all()
        
        # Calcular total de despesas reais (apenas despesas cadastradas)
        total_despesas = sum(d.valor for d in despesas_partida)
        
        # Criar dicionário de participações para o template
        participacoes_existentes = {p.id: p for p in participacoes}
        
        # Buscar todos os jogadores para o select de adicionar
        todos_jogadores = Jogador.query.order_by(Jogador.nome).all()
        
        # Criar conjunto de IDs de jogadores já no jogo para filtro
        jogadores_no_jogo = set(p.jogador_id for p in participacoes)
        
        return render_template('presencas.html', 
                             jogo=jogo, 
                             participacoes=participacoes,
                             participacoes_existentes=participacoes_existentes,
                             todos_jogadores=todos_jogadores,
                             jogadores_no_jogo=jogadores_no_jogo,
                             total_arrecadado=total_arrecadado,
                             total_despesas=total_despesas,
                             total_confirmados=total_confirmados,
                             despesas_partida=despesas_partida)
    
    except Exception as e:
        logger.error(f"Erro ao carregar presenças: {e}")
        flash('Erro ao carregar página de presenças', 'danger')
        return redirect(url_for('jogos'))

@app.route('/extornar-despesa/<int:despesa_id>', methods=['POST'])
def extornar_despesa(despesa_id):
    """Extorna uma despesa do sistema"""
    despesa = Financeiro.query.get_or_404(despesa_id)
    
    if despesa.tipo != 'DESPESA':
        flash('Apenas despesas podem ser extornadas', 'danger')
        return redirect(url_for('jogos'))
    
    try:
        db.session.delete(despesa)
        db.session.commit()
        flash('Despesa extornada com sucesso!', 'success')
        logger.info(f"Despesa {despesa_id} extornada")
    except Exception as e:
        db.session.rollback()
        flash('Erro ao extornar despesa', 'danger')
        logger.error(f"Erro ao extornar despesa: {e}")
    
    return redirect(url_for('jogos'))

@app.route('/pdf-partida/<int:jogo_id>')
def pdf_partida(jogo_id):
    """Gera PDF com dados completos da partida"""
    try:
        jogo = Jogo.query.get_or_404(jogo_id)
        participacoes = Participacao.query.filter_by(jogo_id=jogo_id).all()
        
        # Criar buffer para PDF
        from io import BytesIO
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.darkblue,
            alignment=1,  # centro
            spaceAfter=20
        )
        
        # Conteúdo do PDF
        story = []
        
        # Título
        story.append(Paragraph("RELATÓRIO DA PARTIDA", title_style))
        story.append(Spacer(1, 20))
        
        # Informações básicas
        info_data = [
            ['Adversário:', jogo.adversario or 'Não informado'],
            ['Data:', jogo.data.strftime('%d/%m/%Y')],
            ['Local:', jogo.local or 'Não informado']
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Estatísticas simples
        confirmados = sum(1 for p in participacoes if p.confirmou)
        pagantes = sum(1 for p in participacoes if p.pagou)
        total_arrecadado = sum(p.valor_pago for p in participacoes if p.pagou)
        
        stats_data = [
            ['Confirmados:', str(confirmados)],
            ['Pagantes:', str(pagantes)],
            ['Total Arrecadado:', f'R$ {total_arrecadado:.2f}']
        ]
        
        stats_table = Table(stats_data, colWidths=[2*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(stats_table)
        story.append(Spacer(1, 20))
        
        # Tabela de Jogadores
        if participacoes:
            story.append(Paragraph("DETALHES DOS JOGADORES", styles['Heading2']))
            story.append(Spacer(1, 10))
            
            # Cabeçalho da tabela
            headers = ['Jogador', 'Tipo', 'Confirmou', 'Pagou', 'Valor']
            data = [headers]
            
            # Dados dos jogadores
            for p in participacoes:
                try:
                    data.append([
                        p.jogador.nome if p.jogador else 'Não informado',
                        p.jogador.tipo if p.jogador else 'Não informado',
                        'Sim' if p.confirmou else 'Não',
                        'Sim' if p.pagou else 'Não',
                        f'R$ {p.valor_pago:.2f}' if p.pagou else 'R$ 0.00'
                    ])
                except Exception as e:
                    logger.error(f"Erro ao processar participacao {p.id}: {e}")
                    continue
            
            # Criar tabela apenas se houver dados
            if len(data) > 1:
                table = Table(data, colWidths=[2.5*inch, 1*inch, 0.8*inch, 0.8*inch, 0.8*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Nome do jogador alinhado à esquerda
                ]))
                
                story.append(table)
            story.append(Spacer(1, 20))
        
        # Despesas Detalhadas
        try:
            data_jogo = jogo.data.strftime('%d/%m/%Y')
            despesas_partida = Financeiro.query.filter(
                Financeiro.descricao.like(f"Despesa Jogo {data_jogo}%")
            ).all()
            
            if despesas_partida:
                story.append(Paragraph("DESPESAS DETALHADAS", styles['Heading2']))
                story.append(Spacer(1, 10))
                
                # Cabeçalho da tabela de despesas
                despesa_headers = ['Categoria', 'Descrição', 'Valor']
                despesa_data = [despesa_headers]
                
                # Dados das despesas
                for despesa in despesas_partida:
                    try:
                        # Extrair descrição limpa
                        descricao = despesa.descricao.replace(f"Despesa Jogo {data_jogo}: ", "")
                        
                        # Validar valor da despesa
                        try:
                            valor = float(despesa.valor) if despesa.valor else 0.0
                        except (ValueError, TypeError):
                            valor = 0.0
                        
                        despesa_data.append([
                            despesa.tipo or 'Não informado',
                            descricao or 'Sem descrição',
                            f'R$ {valor:.2f}'
                        ])
                    except Exception as e:
                        logger.error(f"Erro ao processar despesa {despesa.id}: {e}")
                        continue
                
                # Criar tabela apenas se houver dados
                if len(despesa_data) > 1:
                    despesa_table = Table(despesa_data, colWidths=[1.5*inch, 3*inch, 1*inch])
                    despesa_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.lightpink),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('ALIGN', (0, 1), (1, -1), 'LEFT'),  # Categoria e Descrição alinhados à esquerda
                        ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Valor alinhado ao centro
                    ]))
                    
                    story.append(despesa_table)
                    story.append(Spacer(1, 20))
        except Exception as e:
            logger.error(f"Erro ao processar despesas: {e}")
        
        # Craque da partida (se houver)
        if jogo.craque:
            try:
                craque_info = Paragraph(f"<b>CRAQUE DA PARTIDA:</b> {jogo.craque.nome}", styles['Heading3'])
                story.append(craque_info)
                story.append(Spacer(1, 10))
            except Exception as e:
                logger.error(f"Erro ao processar craque: {e}")
        
        # Resumo técnico (se houver)
        if jogo.resumo_texto:
            try:
                story.append(Paragraph("RESUMO TÉCNICO", styles['Heading3']))
                story.append(Spacer(1, 10))
                resumo = Paragraph(jogo.resumo_texto, styles['Normal'])
                story.append(resumo)
                story.append(Spacer(1, 10))
            except Exception as e:
                logger.error(f"Erro ao processar resumo: {e}")
        
        # Rodapé
        story.append(Spacer(1, 30))
        footer = Paragraph(f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal'])
        story.append(footer)
        
        # Gerar PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Configurar resposta PDF
        response = make_response()
        response.data = pdf_data
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=partida_{jogo.adversario}_{jogo.data.strftime("%d_%m_%Y")}.pdf'
        response.headers['Content-Length'] = len(pdf_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
        return redirect(url_for('jogos'))

@app.route('/resumo-jogo/<int:jogo_id>', methods=['GET','POST'])
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

@app.route('/cadastrar-senha-socio', methods=['GET', 'POST'])
@login_required
def cadastrar_senha_socio():
    """Permite que sócios cadastrem suas próprias senhas de acesso"""
    if request.method == 'POST':
        try:
            # Se for admin, pode cadastrar senha para qualquer sócio
            # Se for jogador, só pode cadastrar própria senha
            if not current_user.is_admin():
                jogador_id = current_user.jogador_id
            else:
                jogador_id = int(request.form.get('jogador_id'))
            
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if not password or not confirm_password:
                flash('Por favor, preencha todos os campos', 'danger')
                return redirect(url_for('cadastrar_senha_socio'))
            
            if password != confirm_password:
                flash('As senhas não coincidem', 'danger')
                return redirect(url_for('cadastrar_senha_socio'))
            
            if len(password) < 6:
                flash('A senha deve ter pelo menos 6 caracteres', 'danger')
                return redirect(url_for('cadastrar_senha_socio'))
            
            # Verificar se o jogador existe
            jogador = Jogador.query.get_or_404(jogador_id)
            
            # Verificar se já existe usuário para este jogador
            user_existente = User.query.filter_by(jogador_id=jogador_id).first()
            
            if user_existente:
                # Atualizar senha existente
                user_existente.set_password(password)
                user_existente.is_active = True
                flash(f'Senha do sócio "{jogador.nome}" atualizada com sucesso!', 'success')
                logger.info(f"Senha atualizada para o jogador {jogador.id}")
            else:
                # Criar novo usuário
                # Gerar username único baseado no nome
                username_base = jogador.nome.lower().replace(' ', '_')
                username = username_base
                counter = 1
                while User.query.filter_by(username=username).first():
                    username = f"{username_base}_{counter}"
                    counter += 1
                
                # Gerar email único
                email_base = f"{username_base}@associacao.com"
                email = email_base
                counter = 1
                while User.query.filter_by(email=email).first():
                    email = f"{username_base}_{counter}@associacao.com"
                    counter += 1
                
                novo_user = User(
                    username=username,
                    email=email,
                    role='jogador',
                    jogador_id=jogador_id,
                    is_active=True
                )
                novo_user.set_password(password)
                db.session.add(novo_user)
                flash(f'Conta criada para o sócio "{jogador.nome}" com sucesso!', 'success')
                logger.info(f"Nova conta criada para o jogador {jogador.id}")
            
            db.session.commit()
            return redirect(url_for('jogadores'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao cadastrar senha', 'danger')
            logger.error(f"Erro ao cadastrar senha: {e}")
    
    # GET - Mostrar formulário
    if current_user.is_admin():
        # Admin pode selecionar qualquer sócio sem usuário
        socios_sem_user = db.session.query(Jogador).outerjoin(User).filter(
            Jogador.tipo == 'SOCIO',
            User.jogador_id.is_(None)
        ).all()
        
        socios_com_user = db.session.query(Jogador).join(User).filter(
            Jogador.tipo == 'SOCIO'
        ).all()
        
        return render_template('cadastrar_senha_socio.html', 
                             socios_sem_user=socios_sem_user,
                             socios_com_user=socios_com_user)
    else:
        # Jogador só pode cadastrar própria senha
        if not current_user.jogador_id:
            flash('Você não está associado a nenhum jogador', 'danger')
            return redirect(url_for('index'))
        
        jogador = Jogador.query.get(current_user.jogador_id)
        return render_template('cadastrar_senha_socio.html', jogador=jogador)

@app.route('/jogadores', methods=['GET', 'POST'])
@login_required
def jogadores():
    """Lista e cadastra jogadores"""
    try:
        # Forçar refresh do banco para garantir dados atualizados
        forcar_refresh_banco()
        
        if request.method == 'POST':
            # Verificar permissão para operações de escrita
            if not current_user.is_admin():
                flash('Apenas administradores podem cadastrar ou editar jogadores', 'danger')
                return redirect(url_for('jogadores'))
            
            try:
                # Verificar se é uma edição
                if 'editar_id' in request.form:
                    # Edição de jogador existente
                    jogador_id = int(request.form['editar_id'])
                    jogador = Jogador.query.get(jogador_id)
                    
                    if not jogador:
                        flash('Jogador não encontrado', 'danger')
                        return redirect(url_for('jogadores'))
                    
                    # Atualizar dados
                    jogador.nome = request.form.get('nome', '').strip()
                    jogador.telefone = request.form.get('telefone', '').strip()
                    jogador.tipo = request.form.get('tipo', 'SOCIO')
                    jogador.ativo = 'ativo' in request.form
                    jogador.nativo = 'nativo' in request.form
                    
                    db.session.commit()
                    flash('Jogador atualizado com sucesso!', 'success')
                    return redirect(url_for('jogadores'))
                else:
                    # Novo jogador
                    nome = request.form.get('nome', '').strip()
                    if not nome:
                        flash('Nome é obrigatório', 'danger')
                        return redirect(url_for('jogadores'))
                    
                    # Criar novo jogador
                    novo_jogador = Jogador(
                        nome=nome,
                        telefone=request.form.get('telefone', '').strip(),
                        tipo=request.form.get('tipo', 'SOCIO'),
                        ativo='ativo' in request.form,
                        nativo='nativo' in request.form
                    )
                    
                    db.session.add(novo_jogador)
                    db.session.commit()
                    flash('Jogador cadastrado com sucesso!', 'success')
                    return redirect(url_for('jogadores'))
                    
            except ValueError as e:
                db.session.rollback()
                flash(f'Erro de validação: {str(e)}', 'danger')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Erro ao salvar jogador: {e}")
                flash('Erro ao salvar jogador', 'danger')
        
        # GET - Listar jogadores
        jogadores = Jogador.query.order_by(Jogador.nome).all()
        return render_template('jogadores.html', 
                             jogadores=jogadores,
                             nome_padrao="",
                             telefone_padrao="",
                             tipo_padrao="SOCIO",
                             ativo_padrao=True,
                             nativo_padrao=False)
        
    except Exception as e:
        logger.error(f"Erro ao carregar lista de jogadores: {e}")
        flash('Erro ao carregar lista de jogadores', 'danger')
        return render_template('jogadores.html', jogadores=[])
    """Retorna informações completas do jogador em formato JSON para edição via AJAX"""
    # Verificar se é requisição AJAX
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Se não for AJAX, redirecionar para login
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
    
    # Verificar autenticação
    if not current_user.is_authenticated:
        return jsonify({'error': 'Não autenticado'}), 401
    
    try:
        print(f"DEBUG: Buscando jogador {jogador_id}")
        print(f"DEBUG: Usuário logado: {current_user.username}")
        
        jogador = Jogador.query.get(jogador_id)
        if not jogador:
            print(f"DEBUG: Jogador {jogador_id} não encontrado")
            return jsonify({'error': 'Jogador não encontrado'}), 404
            
        print(f"DEBUG: Jogador encontrado: {jogador.nome}")
        
        return jsonify({
            'id': jogador.id,
            'nome': jogador.nome,
            'telefone': jogador.telefone,
            'tipo': jogador.tipo,
            'ativo': jogador.ativo,
            'nativo': jogador.nativo
        })
    except Exception as e:
        print(f"DEBUG: Exceção em jogador_dados: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        logger.error(f"Erro ao obter informações do jogador {jogador_id}: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@app.route('/toggle_ativo/<int:jogador_id>', methods=['POST'])
def toggle_ativo(jogador_id):
    """Alterna o status ativo/inativo de um jogador"""
    try:
        jogador = Jogador.query.get_or_404(jogador_id)
        jogador.ativo = not jogador.ativo
        db.session.commit()
        
        status = "ativado" if jogador.ativo else "desativado"
        flash(f'Jogador "{jogador.nome}" foi {status} com sucesso!', 'success')
        logger.info(f"Jogador {jogador.nome} {status}")
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao alterar status do jogador', 'danger')
        logger.error(f"Erro ao alterar status do jogador: {e}")
    
    return redirect(url_for('jogadores'))

@app.route('/remover_jogador_partida/<int:jogo_id>/<int:jogador_id>', methods=['POST'])
def remover_jogador_partida(jogo_id, jogador_id):
    """Remove um jogador da participação de um jogo"""
    try:
        participacao = Participacao.query.filter_by(jogo_id=jogo_id, jogador_id=jogador_id).first()
        if participacao:
            jogador_nome = participacao.jogador.nome
            db.session.delete(participacao)
            db.session.commit()
            flash(f'Jogador "{jogador_nome}" removido do jogo com sucesso!', 'success')
            logger.info(f"Jogador {jogador_nome} removido do jogo {jogo_id}")
        else:
            flash('Participação não encontrada', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash('Erro ao remover jogador do jogo', 'danger')
        logger.error(f"Erro ao remover jogador do jogo: {e}")
    
    return redirect(url_for('presencas', jogo_id=jogo_id))

@app.route('/associados', methods=['GET', 'POST'])
@login_required
def associados():
    """Controle de mensalidades com filtros"""
    socios = Jogador.query.filter_by(tipo='SOCIO').order_by(Jogador.nome).all()
    
    # Parâmetros de filtro
    filtro_mes = request.args.get('mes', '')
    filtro_ano = request.args.get('ano', '')
    filtro_socio = request.args.get('socio_id', '')
    
    if request.method == 'POST':
        # Verificar permissão - apenas admins podem lançar mensalidades
        if not current_user.is_admin():
            flash('Apenas administradores podem lançar mensalidades', 'danger')
            return redirect(url_for('associados'))
        
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
            nova_mensalidade = Financeiro(
                data=date.today(),
                tipo='MENSALIDADE',
                descricao=f"Mensalidade {mes}/{ano} - {jogador.nome}",
                valor=valor,
                jogador_id=jogador.id,
                mes_referencia=mes_ano,
                ano_referencia=ano_int
            )
            
            db.session.add(nova_mensalidade)
            db.session.commit()
            
            # Verificar se a mensalidade foi realmente salva
            mensalidade_salva = Financeiro.query.filter_by(id=nova_mensalidade.id).first()
            logger.info(f"Mensalidade salva no banco: {mensalidade_salva}")
            
            # Forçar refresh para garantir que os dados apareçam na lista
            db.session.refresh(nova_mensalidade)
            db.session.expire_all()
            
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
    
    # Construir query base com filtros
    # Forçar refresh do banco para garantir dados atualizados
    db.session.expire_all()
    db.session.flush()
    
    query = Financeiro.query.filter_by(tipo='MENSALIDADE')
    
    # Aplicar filtros se existirem
    if filtro_mes:
        query = query.filter(Financeiro.mes_referencia.like(f'%{filtro_mes}%'))
    if filtro_ano:
        query = query.filter(Financeiro.ano_referencia == int(filtro_ano) if filtro_ano.isdigit() else None)
    if filtro_socio:
        query = query.filter(Financeiro.jogador_id == int(filtro_socio) if filtro_socio.isdigit() else None)
    
    # Buscar mensalidades filtradas
    mensalidades_filtradas = query.order_by(Financeiro.ano_referencia.desc(), Financeiro.mes_referencia.desc()).all()
    
    # Agrupar por sócio
    mensalidades_por_socio = {}
    for mensalidade in mensalidades_filtradas:
        socio_id = mensalidade.jogador_id
        if socio_id not in mensalidades_por_socio:
            mensalidades_por_socio[socio_id] = {
                'socio': mensalidade.jogador,
                'mensalidades': [],
                'total_pago': 0
            }
        
        mensalidades_por_socio[socio_id]['mensalidades'].append(mensalidade)
        mensalidades_por_socio[socio_id]['total_pago'] += mensalidade.valor
    
    # Obter anos únicos para o filtro
    anos = sorted(set(
        m.ano_referencia for m in Financeiro.query.filter_by(tipo='MENSALIDADE')
        .filter(Financeiro.ano_referencia.isnot(None)).all()
    ), reverse=True)
    
    # Obter meses únicos para o filtro
    meses = sorted(set(
        m.mes_referencia for m in Financeiro.query.filter_by(tipo='MENSALIDADE')
        .filter(Financeiro.mes_referencia.isnot(None)).all()
    ))
    
    # Calcular total geral (apenas dos filtrados)
    total_geral = sum(dados['total_pago'] for dados in mensalidades_por_socio.values())
    
    # Valores atuais dos filtros para o formulário
    filtros_atuais = {
        'mes': filtro_mes,
        'ano': filtro_ano,
        'socio_id': filtro_socio
    }
    
    return render_template('associados.html', 
                         socios=socios,
                         mensalidades_por_socio=mensalidades_por_socio,
                         anos=anos,
                         meses=meses,
                         total_geral=total_geral,
                         filtros=filtros_atuais,
                         ano_atual=date.today().year,
                         mes_atual=date.today().strftime('%B'),
                         valor_padrao="50.00")



@app.route('/pdf-mensalidades')
def pdf_mensalidades():
    """Gera PDF com controle de mensalidades por sócio e ano"""
    try:
        # Gerar PDF
        from reportlab.platypus import PageBreak
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from io import BytesIO
        
        # Obter parâmetros
        filtro_ano = request.args.get('ano', '')
        
        # Buscar sócios
        socios = Jogador.query.filter_by(tipo='SOCIO').order_by(Jogador.nome).all()
        
        # Buscar mensalidades
        query = Financeiro.query.filter_by(tipo='MENSALIDADE')
        if filtro_ano and filtro_ano.isdigit():
            query = query.filter(Financeiro.ano_referencia == int(filtro_ano))
        
        mensalidades = query.order_by(Financeiro.ano_referencia.desc(), Financeiro.mes_referencia.desc()).all()
        
        # Agrupar mensalidades por sócio e ano
        dados_socios = {}
        anos_disponiveis = set()
        
        for mens in mensalidades:
            if mens.jogador_id not in dados_socios:
                dados_socios[mens.jogador_id] = {
                    'nome': mens.jogador.nome,
                    'anos': {}
                }
            
            ano = mens.ano_referencia or 0
            anos_disponiveis.add(ano)
            
            if ano not in dados_socios[mens.jogador_id]['anos']:
                dados_socios[mens.jogador_id]['anos'][ano] = {}
            
            # Extrair mês do formato "MM/YYYY" ou "Mês/YYYY"
            mes_ref = mens.mes_referencia or ''
            mes_num = ''
            if '/' in mes_ref:
                mes_nome_completo = mes_ref.split('/')[0]
                
                # Mapeamento de nomes para números
                nome_para_num = {
                    'Janeiro': '01', 'Fevereiro': '02', 'Março': '03', 'Marco': '03',
                    'Abril': '04', 'Maio': '05', 'Junho': '06', 'Julho': '07',
                    'Agosto': '08', 'Setembro': '09', 'Outubro': '10', 'Novembro': '11', 'Dezembro': '12'
                }
                
                # Verificar se é nome do mês ou número
                if mes_nome_completo in nome_para_num:
                    mes_num = nome_para_num[mes_nome_completo]
                    mes_nome = {
                        '01': 'Jan', '02': 'Fev', '03': 'Mar', '04': 'Abr',
                        '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Ago',
                        '09': 'Set', '10': 'Out', '11': 'Nov', '12': 'Dez'
                    }.get(mes_num, mes_num)
                elif len(mes_nome_completo) == 2 and mes_nome_completo.isdigit():
                    mes_num = mes_nome_completo
                    mes_nome = {
                        '01': 'Jan', '02': 'Fev', '03': 'Mar', '04': 'Abr',
                        '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Ago',
                        '09': 'Set', '10': 'Out', '11': 'Nov', '12': 'Dez'
                    }.get(mes_num, mes_num)
                else:
                    mes_num = mes_nome_completo
                    mes_nome = mes_nome_completo
            else:
                mes_nome = mes_ref
                mes_num = ''  # Define como vazio se não conseguir extrair
            
            dados_socios[mens.jogador_id]['anos'][ano][mes_num] = {
                'nome': mes_nome,
                'pago': True,
                'valor': mens.valor
            }
        
        # Criar buffer para PDF
        buffer = BytesIO()
        from reportlab.lib.pagesizes import A4, landscape
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), 
                               leftMargin=15, rightMargin=15, 
                               topMargin=25, bottomMargin=25)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.darkblue,
            alignment=1,  # centro
            spaceAfter=12
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.black,
            alignment=1,
            spaceAfter=6
        )
        
        # Conteúdo do PDF
        story = []
        
        # Título
        titulo = "CONTROLE DE MENSALIDADES"
        if filtro_ano and filtro_ano.isdigit():
            titulo += f" - ANO {filtro_ano}"
        story.append(Paragraph(titulo, title_style))
        story.append(Spacer(1, 12))
        
        # Ordenar anos
        anos_ordenados = sorted(anos_disponiveis, reverse=True)
        
        # Para cada ano disponível
        for idx_ano, ano in enumerate(anos_ordenados):
            story.append(Paragraph(f"ANO {ano}", header_style))
            story.append(Spacer(1, 3))
            
            # Verificar se há dados para este ano
            tem_dados_ano = any(ano in dados_socios[socio_id]['anos'] 
                                   for socio_id in dados_socios.keys())
            
            if not tem_dados_ano:
                story.append(Paragraph("Nenhuma mensalidade encontrada para este ano.", 
                                    styles['Normal']))
                story.append(Spacer(1, 10))
                
                # Adicionar quebra de página a cada 3 anos (exceto no último)
                if idx_ano > 0 and (idx_ano + 1) % 3 == 0 and idx_ano < len(anos_ordenados) - 1:
                    story.append(PageBreak())
                    continue
            
            # Cabeçalho da tabela
            headers = ['Sócio'] + [
                ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 
                     'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
                ][0] + ['Total']
            
            # Dados da tabela
            table_data = [headers]
            
            # Para cada sócio
            for socio_id in sorted(dados_socios.keys()):
                socio = dados_socios[socio_id]
                # Truncar nome se for muito longo (mais espaço em paisagem)
                nome_socio = socio['nome'][:35] + ('...' if len(socio['nome']) > 35 else '')
                row = [nome_socio]
                total_ano = 0
                
                # Para cada mês
                for mes_num in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']:
                    if ano in socio['anos'] and mes_num in socio['anos'][ano]:
                        mes_data = socio['anos'][ano][mes_num]
                        row.append(f"R$ {mes_data['valor']:.0f}")
                        total_ano += mes_data['valor']
                    else:
                        row.append('-')
                
                row.append(f"R$ {total_ano:.0f}")
                table_data.append(row)
            
            # Calcular larguras das colunas para paisagem (total ~11.5 polegadas)
            col_widths = [2.2*inch] + [0.65*inch] * 12 + [0.85*inch]
            
            # Criar tabela
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            # Estilo da tabela
            estilo_tabela = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
                ('TOPPADDING', (0, 0), (-1, 0), 3),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
            ]
            
            # Destacar primeira coluna (nome) e última (total)
            for i in range(1, len(table_data)):
                estilo_tabela.append(('ALIGN', (0, i), (0, i), 'LEFT'))
                estilo_tabela.append(('FONTNAME', (0, i), (0, i), 'Helvetica'))
                estilo_tabela.append(('FONTSIZE', (0, i), (0, i), 7))
                # Destacar coluna total
                estilo_tabela.append(('BACKGROUND', (-1, i), (-1, i), colors.lightgrey))
                estilo_tabela.append(('FONTNAME', (-1, i), (-1, i), 'Helvetica-Bold'))
            
            table.setStyle(TableStyle(estilo_tabela))
            story.append(table)
            
            # Verificar se há muitos sócios para quebra automática
            total_socios = len(dados_socios)
            max_linhas_sem_quebra = 25  # Máximo de linhas antes de quebrar
            
            # Adicionar quebra automática se muitos sócios ou próximo ano
            if (len(table_data) > max_linhas_sem_quebra or 
                    idx_ano < len(anos_ordenados) - 1):
                story.append(PageBreak())
            else:
                story.append(Spacer(1, 15))
        
        # Rodapé centralizado (na mesma página)
        footer_style = ParagraphStyle(
            'CustomFooter',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=1,  # centro
            spaceBefore=30  # Mais espaço antes do rodapé
        )
        
        data_geracao = date.today().strftime('%d/%m/%Y %H:%M')
        footer_text = f"Gerado em {data_geracao} - Sistema de Gestão da Associação"
        story.append(Paragraph(footer_text, footer_style))
        
        doc.build(story)
        
        # Preparar resposta
        buffer.seek(0)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=controle_mensalidades_{filtro_ano or "todos"}.pdf'
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF de mensalidades: {e}")
        flash('Erro ao gerar PDF de mensalidades', 'danger')
        return redirect(url_for('associados'))
@app.route('/adicionar-entrada', methods=['POST'])
@login_required
def adicionar_entrada():
    """Adiciona uma entrada no caixa"""
    # Verificar permissão - apenas admins podem lançar entradas
    if not current_user.is_admin():
        flash('Apenas administradores podem lançar entradas', 'danger')
        return redirect(url_for('financeiro'))
    
    try:
        descricao = request.form.get('descricao', '').strip()
        valor = request.form.get('valor')
        
        if not descricao or not valor:
            flash('Descrição e valor são obrigatórios', 'warning')
            return redirect(url_for('financeiro'))
        
        valor = validar_valor(valor)
        
        db.session.add(Financeiro(
            data=date.today(),
            tipo='ENTRADA',
            descricao=descricao,
            valor=valor
        ))
        db.session.commit()
        flash('Entrada adicionada com sucesso!', 'success')
        logger.info(f"Entrada adicionada: {descricao} - R$ {valor}")
        return redirect(url_for('financeiro'))
        
    except ValueError as e:
        db.session.rollback()
        flash(f'Erro de validação: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao adicionar entrada', 'danger')
        logger.error(f"Erro ao adicionar entrada: {e}")
        return redirect(url_for('financeiro'))

@app.route('/adicionar-despesa', methods=['POST'])
@login_required
def adicionar_despesa():
    """Adiciona uma despesa no caixa"""
    # Verificar permissão - apenas admins podem lançar despesas
    if not current_user.is_admin():
        flash('Apenas administradores podem lançar despesas', 'danger')
        return redirect(url_for('financeiro'))
    
    try:
        categoria = request.form.get('categoria', '').strip()
        descricao = request.form.get('descricao', '').strip()
        valor = request.form.get('valor')
        
        if not categoria or not descricao or not valor:
            flash('Categoria, descrição e valor são obrigatórios', 'warning')
            return redirect(url_for('financeiro'))
        
        valor = validar_valor(valor)
        
        db.session.add(Financeiro(
            data=date.today(),
            tipo='DESPESA',
            descricao=f"{categoria}: {descricao}",
            valor=valor
        ))
        db.session.commit()
        
        flash('Despesa adicionada com sucesso!', 'success')
        logger.info(f"Despesa adicionada: {categoria} - {descricao} - R$ {valor}")
        
    except ValueError as e:
        flash(f'Valor inválido: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao adicionar despesa', 'danger')
        logger.error(f"Erro ao adicionar despesa: {e}")
    
    return redirect(url_for('financeiro'))

@app.route('/extornar-movimentacao/<int:movimentacao_id>', methods=['POST'])
def extornar_movimentacao(movimentacao_id):
    """Extorna uma movimentação (entrada ou despesa)"""
    try:
        movimentacao = Financeiro.query.get_or_404(movimentacao_id)
        
        # Não permite extornar mensalidades e pagamentos de partidas
        if movimentacao.tipo in ['MENSALIDADE', 'PARTIDA']:
            flash('Esta movimentação não pode ser extornada', 'danger')
            return redirect(url_for('financeiro'))
        
        # Obter motivo do formulário
        motivo = request.form.get('motivo', '').strip()
        if not motivo:
            flash('Motivo do extorno é obrigatório', 'warning')
            return redirect(url_for('financeiro'))
        
        # Salvar dados originais para auditoria
        import json
        dados_originais = {
            'id': movimentacao.id,
            'data': movimentacao.data.strftime('%d/%m/%Y'),
            'tipo': movimentacao.tipo,
            'descricao': movimentacao.descricao,
            'valor': movimentacao.valor,
            'jogador_id': movimentacao.jogador_id
        }
        
        # Criar registro de auditoria
        auditoria = Auditoria(
            acao='EXTORNO_MOVIMENTACAO',
            tabela_afetada='financeiro',
            registro_id=movimentacao.id,
            motivo=motivo,
            dados_originais=json.dumps(dados_originais, ensure_ascii=False)
        )
        
        descricao = movimentacao.descricao
        valor = movimentacao.valor
        
        # Remover movimentação e salvar auditoria
        db.session.add(auditoria)
        db.session.delete(movimentacao)
        db.session.commit()
        
        flash('Movimentação extornada com sucesso!', 'success')
        logger.info(f"Movimentação extornada: {descricao} - R$ {valor} - Motivo: {motivo}")
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao extornar movimentação', 'danger')
        logger.error(f"Erro ao extornar movimentação: {e}")
    
    return redirect(url_for('financeiro'))

@app.route('/auditoria')
def auditoria():
    """Página de auditoria de extornos e alterações"""
    try:
        # Buscar registros de auditoria
        registros = Auditoria.query.order_by(Auditoria.data_hora.desc()).limit(100).all()
        
        return render_template('auditoria.html', registros=registros)
    except Exception as e:
        logger.error(f"Erro ao carregar auditoria: {e}")
        flash('Erro ao carregar auditoria', 'danger')
        return redirect(url_for('financeiro'))

@app.route('/pdf-caixa-periodo')
def pdf_caixa_periodo():
    """Gera PDF com extrato do caixa filtrado por período"""
    try:
        # Obter filtros da URL
        data_inicio_str = request.args.get('data_inicio', '')
        data_fim_str = request.args.get('data_fim', '')
        tipo_filtro = request.args.get('tipo', '')
        
        # Construir query base
        query = Financeiro.query
        
        # Aplicar filtros de data se fornecidos
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                query = query.filter(Financeiro.data >= data_inicio)
            except ValueError:
                flash('Data inicial inválida', 'warning')
                return redirect(url_for('financeiro'))
        
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
                query = query.filter(Financeiro.data <= data_fim)
            except ValueError:
                flash('Data final inválida', 'warning')
                return redirect(url_for('financeiro'))
        
        # Aplicar filtro por tipo se fornecido
        if tipo_filtro == 'entradas':
            query = query.filter(Financeiro.tipo != 'DESPESA')
        elif tipo_filtro == 'despesas':
            query = query.filter(Financeiro.tipo == 'DESPESA')
        
        # Executar query ordenada
        movs = query.order_by(Financeiro.data.desc(), Financeiro.id.desc()).all()
        
        # Calcular totais
        saldo_atual = 0
        total_entradas = 0
        total_despesas = 0
        movimentacoes = []
        
        for m in movs:
            if m.tipo == 'DESPESA':
                saldo_atual -= m.valor
                total_despesas += m.valor
            else:
                saldo_atual += m.valor
                total_entradas += m.valor
                
            movimentacoes.append({
                'mov': m,
                'saldo_acumulado': saldo_atual
            })
        
        # Criar buffer para PDF
        from io import BytesIO
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.darkblue,
            alignment=1,  # centro
            spaceAfter=20
        )
        
        # Conteúdo do PDF
        story = []
        
        # Título com período
        titulo = "EXTRATO DO CAIXA"
        if data_inicio_str or data_fim_str:
            periodo = []
            if data_inicio_str:
                data_inicio_fmt = datetime.strptime(data_inicio_str, '%Y-%m-%d').strftime('%d/%m/%Y')
                periodo.append(f"de {data_inicio_fmt}")
            if data_fim_str:
                data_fim_fmt = datetime.strptime(data_fim_str, '%Y-%m-%d').strftime('%d/%m/%Y')
                periodo.append(f"até {data_fim_fmt}")
            titulo += f" - {' '.join(periodo)}"
        
        story.append(Paragraph(titulo, title_style))
        story.append(Spacer(1, 20))
        
        # Resumo Financeiro
        story.append(Paragraph("RESUMO FINANCEIRO", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        resumo_data = [
            ['Total Entradas:', f'R$ {total_entradas:.2f}'],
            ['Total Despesas:', f'R$ {total_despesas:.2f}'],
            ['SALDO DO PERÍODO:', f'R$ {saldo_atual:.2f}']
        ]
        
        resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (2, 0), (2, 0), colors.lightgreen if saldo_atual >= 0 else colors.lightcoral),
            ('TEXTCOLOR', (2, 0), (2, 0), colors.black),
        ]))
        
        story.append(resumo_table)
        story.append(Spacer(1, 20))
        
        # Extrato Detalhado
        story.append(Paragraph("EXTRATO DETALHADO", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        # Cabeçalho da tabela
        headers = ['Data', 'Tipo', 'Descrição', 'Valor', 'Saldo Acumulado']
        data = [headers]
        
        # Dados das movimentações
        for item in movimentacoes:
            m = item['mov']
            
            # Formatar tipo
            if m.tipo == 'MENSALIDADE':
                tipo = 'Mensalidade'
            elif m.tipo == 'PARTIDA':
                tipo = 'Partida'
            elif m.tipo == 'ENTRADA':
                tipo = 'Entrada'
            else:
                tipo = 'Despesa'
            
            # Formatar valor
            if m.tipo == 'DESPESA':
                valor_str = f"-R$ {m.valor:.2f}"
            else:
                valor_str = f"R$ {m.valor:.2f}"
            
            # Formatar saldo
            saldo_str = f"R$ {item['saldo_acumulado']:.2f}"
            
            data.append([
                m.data.strftime('%d/%m/%Y'),
                tipo,
                m.descricao,
                valor_str,
                saldo_str
            ])
        
        # Criar tabela apenas se houver dados
        if len(data) > 1:
            table = Table(data, colWidths=[1*inch, 1.2*inch, 3*inch, 1.2*inch, 1.2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Data
                ('ALIGN', (2, 1), (2, -1), 'LEFT'),   # Descrição
                ('ALIGN', (3, 1), (4, -1), 'RIGHT'),  # Valor e Saldo
            ]))
            
            # Alternar cores das linhas
            for i in range(1, len(data)):
                if i % 2 == 0:
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, i), (-1, i), colors.lightgrey)
                    ]))
            
            story.append(table)
        else:
            story.append(Paragraph("Nenhuma movimentação encontrada para o período selecionado.", styles['Normal']))
        
        # Rodapé
        story.append(Spacer(1, 30))
        footer = Paragraph(f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal'])
        story.append(footer)
        
        # Gerar PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Nome do arquivo com período
        if data_inicio_str and data_fim_str:
            filename = f"extrato_caixa_{data_inicio_str}_{data_fim_str}.pdf"
        elif data_inicio_str:
            filename = f"extrato_caixa_desde_{data_inicio_str}.pdf"
        elif data_fim_str:
            filename = f"extrato_caixa_ate_{data_fim_str}.pdf"
        else:
            filename = f"extrato_caixa_{datetime.now().strftime('%d_%m_%Y')}.pdf"
        
        # Configurar resposta PDF
        response = make_response()
        response.data = pdf_data
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Length'] = len(pdf_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF do caixa por período: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
        return redirect(url_for('financeiro'))

@app.route('/pdf-caixa')
def pdf_caixa():
    """Gera PDF com extrato completo do caixa"""
    try:
        # Buscar todas as movimentações
        movs = Financeiro.query.order_by(Financeiro.data.desc(), Financeiro.id.desc()).all()
        
        # Calcular totais
        saldo_atual = 0
        total_entradas = 0
        total_despesas = 0
        movimentacoes = []
        
        for m in movs:
            if m.tipo == 'DESPESA':
                saldo_atual -= m.valor
                total_despesas += m.valor
            else:
                saldo_atual += m.valor
                total_entradas += m.valor
                
            movimentacoes.append({
                'mov': m,
                'saldo_acumulado': saldo_atual
            })
        
        # Criar buffer para PDF
        from io import BytesIO
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.darkblue,
            alignment=1,  # centro
            spaceAfter=20
        )
        
        # Conteúdo do PDF
        story = []
        
        # Título
        story.append(Paragraph("EXTRATO COMPLETO DO CAIXA", title_style))
        story.append(Spacer(1, 20))
        
        # Resumo Financeiro
        story.append(Paragraph("RESUMO FINANCEIRO", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        resumo_data = [
            ['Total Entradas:', f'R$ {total_entradas:.2f}'],
            ['Total Despesas:', f'R$ {total_despesas:.2f}'],
            ['SALDO ATUAL:', f'R$ {saldo_atual:.2f}']
        ]
        
        resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (2, 0), (2, 0), colors.lightgreen if saldo_atual >= 0 else colors.lightcoral),
            ('TEXTCOLOR', (2, 0), (2, 0), colors.black),
        ]))
        
        story.append(resumo_table)
        story.append(Spacer(1, 20))
        
        # Extrato Detalhado
        story.append(Paragraph("EXTRATO DETALHADO", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        # Cabeçalho da tabela
        headers = ['Data', 'Tipo', 'Descrição', 'Valor', 'Saldo Acumulado']
        data = [headers]
        
        # Dados das movimentações
        for item in movimentacoes:
            m = item['mov']
            
            # Formatar tipo
            if m.tipo == 'MENSALIDADE':
                tipo = 'Mensalidade'
                cor_tipo = colors.green
            elif m.tipo == 'PARTIDA':
                tipo = 'Partida'
                cor_tipo = colors.blue
            elif m.tipo == 'ENTRADA':
                tipo = 'Entrada'
                cor_tipo = colors.darkblue
            else:
                tipo = 'Despesa'
                cor_tipo = colors.red
            
            # Formatar valor
            if m.tipo == 'DESPESA':
                valor_str = f"-R$ {m.valor:.2f}"
                cor_valor = colors.red
            else:
                valor_str = f"R$ {m.valor:.2f}"
                cor_valor = colors.green
            
            # Formatar saldo
            saldo_str = f"R$ {item['saldo_acumulado']:.2f}"
            cor_saldo = colors.green if item['saldo_acumulado'] >= 0 else colors.red
            
            data.append([
                m.data.strftime('%d/%m/%Y'),
                tipo,
                m.descricao,
                valor_str,
                saldo_str
            ])
        
        # Criar tabela apenas se houver dados
        if len(data) > 1:
            table = Table(data, colWidths=[1*inch, 1.2*inch, 3*inch, 1.2*inch, 1.2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Data
                ('ALIGN', (2, 1), (2, -1), 'LEFT'),   # Descrição
                ('ALIGN', (3, 1), (4, -1), 'RIGHT'),  # Valor e Saldo
            ]))
            
            # Alternar cores das linhas
            for i in range(1, len(data)):
                if i % 2 == 0:
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, i), (-1, i), colors.lightgrey)
                    ]))
            
            story.append(table)
        
        # Rodapé
        story.append(Spacer(1, 30))
        footer = Paragraph(f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal'])
        story.append(footer)
        
        # Gerar PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Configurar resposta PDF
        response = make_response()
        response.data = pdf_data
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=extrato_caixa_{datetime.now().strftime("%d_%m_%Y")}.pdf'
        response.headers['Content-Length'] = len(pdf_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF do caixa: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
        return redirect(url_for('financeiro'))

@app.route('/financeiro')
@login_required
def financeiro():
    """Extrato financeiro com filtro por período"""
    try:
        # Forçar refresh do banco para garantir dados atualizados
        forcar_refresh_banco()
        
        # Parâmetros de filtros da URL
        data_inicio_str = request.args.get('data_inicio', '')
        data_fim_str = request.args.get('data_fim', '')
        tipo_filtro = request.args.get('tipo', '')
        
        # Criar dicionário de filtros para o template
        filtros = {
            'data_inicio': data_inicio_str,
            'data_fim': data_fim_str,
            'tipo': tipo_filtro
        }
        
        # Construir query base
        query = Financeiro.query
        
        # Aplicar filtros de data se fornecidos
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                query = query.filter(Financeiro.data >= data_inicio)
            except ValueError:
                flash('Data inicial inválida', 'warning')
        
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
                query = query.filter(Financeiro.data <= data_fim)
            except ValueError:
                flash('Data final inválida', 'warning')
        
        # Aplicar filtro por tipo se fornecido
        if tipo_filtro == 'entradas':
            query = query.filter(Financeiro.tipo != 'DESPESA')
        elif tipo_filtro == 'despesas':
            query = query.filter(Financeiro.tipo == 'DESPESA')
        
        # Executar query ordenada
        movs = query.order_by(Financeiro.data.desc(), Financeiro.id.desc()).all()
        
        # Calcular saldo acumulado e totais
        saldo_atual = 0
        total_entradas = 0
        total_despesas = 0
        movimentacoes = []
        
        for m in movs:
            if m.tipo == 'DESPESA':
                saldo_atual -= m.valor
                total_despesas += m.valor
            else:
                saldo_atual += m.valor
                total_entradas += m.valor
                
            movimentacoes.append({
                'mov': m,
                'saldo_acumulado': saldo_atual
            })
        
        descricao_entrada_padrao = ""
        valor_entrada_padrao = "100.00"
        descricao_despesa_padrao = ""
        valor_despesa_padrao = "50.00"
        categoria_despesa_padrao = ""
        
        return render_template('financeiro.html',
                             movimentacoes=movimentacoes,
                             total_entradas=total_entradas,
                             total_despesas=total_despesas,
                             saldo_atual=saldo_atual,
                             filtros=filtros,
                             descricao_entrada_padrao=descricao_entrada_padrao,
                             valor_entrada_padrao=valor_entrada_padrao,
                             descricao_despesa_padrao=descricao_despesa_padrao,
                             valor_despesa_padrao=valor_despesa_padrao,
                             categoria_despesa_padrao=categoria_despesa_padrao)
    except Exception as e:
        logger.error(f"Erro ao carregar financeiro: {e}")
        flash('Erro ao carregar extrato financeiro', 'danger')
        return render_template('financeiro.html', 
                             movimentacoes=[],
                             total_entradas=0,
                             total_despesas=0,
                             saldo_atual=0,
                             filtros={'data_inicio': '', 'data_fim': '', 'tipo': ''})

@app.route('/ranking')
def ranking():
    """Página de ranking dos atletas"""
    try:
        # Forçar refresh do banco para garantir dados atualizados
        forcar_refresh_banco()
        
        # Buscar todos os jogadores
        jogadores = Jogador.query.all()
        
        # Ranking por Presença
        ranking_presenca = []
        for jogador in jogadores:
            participacoes = Participacao.query.filter_by(jogador_id=jogador.id).all()
            
            total_jogos = len(participacoes)
            total_confirmados = sum(1 for p in participacoes if p.confirmou)
            total_pagos = sum(1 for p in participacoes if p.pagou)
            pontuacao = total_confirmados + total_pagos
            
            # Calcular percentual de presença
            perc_presenca = (total_confirmados / total_jogos * 100) if total_jogos > 0 else 0
            
            if total_jogos > 0:
                ranking_presenca.append({
                    'jogador': jogador,
                    'total_jogos': total_jogos,
                    'jogos_confirmados': total_confirmados,
                    'jogos_pagos': total_pagos,
                    'pontuacao': pontuacao,
                    'perc_presenca': perc_presenca
                })
        
        # Ordenar por pontuação (maior para menor)
        ranking_presenca.sort(key=lambda x: x['pontuacao'], reverse=True)
        
        # Ranking Financeiro
        ranking_financeiro = []
        for jogador in jogadores:
            participacoes = Participacao.query.filter_by(jogador_id=jogador.id, pagou=True).all()
            
            total_pago = sum(p.valor_pago for p in participacoes)
            jogos_pagos = len(participacoes)
            media_por_jogo = total_pago / jogos_pagos if jogos_pagos > 0 else 0
            
            if total_pago > 0:
                ranking_financeiro.append({
                    'jogador': jogador,
                    'total_pago': total_pago,
                    'qtd_pagamentos': jogos_pagos,
                    'media_por_jogo': media_por_jogo
                })
        
        # Ordenar por total pago (maior para menor)
        ranking_financeiro.sort(key=lambda x: x['total_pago'], reverse=True)
        
        # Ranking Técnico
        ranking_tecnico = []
        for jogador in jogadores:
            participacoes = Participacao.query.filter_by(jogador_id=jogador.id).all()
            
            total_gols = sum(p.gols or 0 for p in participacoes)
            total_expulsoes = sum(1 for p in participacoes if p.expulso)
            
            # Contar vezes que foi craque
            craques = Jogo.query.filter_by(craque_id=jogador.id).count()
            
            pontuacao = total_gols + craques - total_expulsoes
            
            if total_gols > 0 or craques > 0 or total_expulsoes > 0:
                ranking_tecnico.append({
                    'jogador': jogador,
                    'total_gols': total_gols,
                    'craque_count': craques,
                    'total_expulsoes': total_expulsoes,
                    'pontuacao': pontuacao
                })
        
        # Ordenar por pontuação técnica (maior para menor)
        ranking_tecnico.sort(key=lambda x: x['pontuacao'], reverse=True)
        
        return render_template('ranking.html',
                           ranking_presenca=ranking_presenca,
                           ranking_financeiro=ranking_financeiro,
                           ranking_tecnico=ranking_tecnico)
        
    except Exception as e:
        logger.error(f"Erro ao carregar ranking: {e}")
        flash('Erro ao carregar ranking', 'danger')
        return render_template('ranking.html',
                           ranking_presenca=[],
                           ranking_financeiro=[],
                           ranking_tecnico=[])

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
@login_required
def extornar_mensalidade(mensalidade_id):
    """Extorna (remove) uma mensalidade"""
    # Verificar permissão - apenas admins podem extornar mensalidades
    if not current_user.is_admin():
        flash('Apenas administradores podem extornar mensalidades', 'danger')
        return redirect(url_for('associados'))
    
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

# ================= GERENCIAMENTO DE USUÁRIOS =================

@app.route('/gerenciar-usuarios', methods=['GET'])
@login_required
def gerenciar_usuarios():
    """Página para gerenciar usuários do sistema"""
    # Apenas admins podem acessar
    if not current_user.is_admin():
        flash('Apenas administradores podem gerenciar usuários', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Buscar todos os usuários
        usuarios = User.query.order_by(User.created_at.desc()).all()
        
        # Buscar jogadores que não têm usuário
        jogadores_com_usuario = [u.jogador_id for u in usuarios if u.jogador_id]
        jogadores_sem_usuario = Jogador.query.filter(~Jogador.id.in_(jogadores_com_usuario)).all()
        
        return render_template('gerenciar_usuarios.html', 
                            usuarios=usuarios, 
                            jogadores_sem_usuario=jogadores_sem_usuario)
    except Exception as e:
        logger.error(f"Erro ao carregar gerenciamento de usuários: {e}")
        flash('Erro ao carregar página de usuários', 'danger')
        return redirect(url_for('index'))

@app.route('/promover-admin', methods=['POST'])
@login_required
def promover_admin():
    """Promove um jogador a administrador ou visualizador"""
    # Apenas admins podem promover
    if not current_user.is_admin():
        flash('Apenas administradores podem promover usuários', 'danger')
        return redirect(url_for('gerenciar_usuarios'))
    
    try:
        jogador_id = request.form.get('jogador_id')
        tipo_acesso = request.form.get('tipo_acesso')
        
        if not jogador_id or not tipo_acesso:
            flash('Selecione um jogador e o tipo de acesso', 'warning')
            return redirect(url_for('gerenciar_usuarios'))
        
        jogador = Jogador.query.get(int(jogador_id))
        if not jogador:
            flash('Jogador não encontrado', 'danger')
            return redirect(url_for('gerenciar_usuarios'))
        
        # Verificar se jogador já tem usuário
        usuario_existente = User.query.filter_by(jogador_id=jogador.id).first()
        if usuario_existente:
            # Atualizar tipo de acesso
            usuario_existente.role = tipo_acesso
            db.session.commit()
            flash(f'Acesso de {jogador.nome} atualizado para {tipo_acesso} com sucesso!', 'success')
        else:
            # Criar novo usuário
            username = f"{jogador.nome.lower().replace(' ', '_')}_{jogador.id}"
            email = f"{username}@associacao.local"
            
            novo_usuario = User(
                username=username,
                email=email,
                role=tipo_acesso,
                jogador_id=jogador.id
            )
            novo_usuario.set_password('temp123')  # Senha temporária
            db.session.add(novo_usuario)
            db.session.commit()
            
            flash(f'{jogador.nome} promovido para {tipo_acesso} com sucesso! Senha temporária: temp123', 'success')
            logger.info(f"Usuário criado: {jogador.nome} - {tipo_acesso}")
        
        return redirect(url_for('gerenciar_usuarios'))
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao promover usuário', 'danger')
        logger.error(f"Erro ao promover usuário: {e}")
        return redirect(url_for('gerenciar_usuarios'))

@app.route('/remover-usuario/<int:usuario_id>', methods=['POST'])
@login_required
def remover_usuario(usuario_id):
    """Remove um usuário do sistema"""
    # Apenas admins podem remover
    if not current_user.is_admin():
        flash('Apenas administradores podem remover usuários', 'danger')
        return redirect(url_for('gerenciar_usuarios'))
    
    try:
        usuario = User.query.get_or_404(usuario_id)
        
        # Não permitir remover o admin principal
        if usuario.username == 'admin':
            flash('Não é possível remover o usuário administrador principal', 'warning')
            return redirect(url_for('gerenciar_usuarios'))
        
        jogador_nome = usuario.jogador.nome if usuario.jogador else 'Desconhecido'
        db.session.delete(usuario)
        db.session.commit()
        
        flash(f'Usuário {usuario.username} removido com sucesso!', 'success')
        logger.info(f"Usuário removido: {usuario.username}")
        return redirect(url_for('gerenciar_usuarios'))
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao remover usuário', 'danger')
        logger.error(f"Erro ao remover usuário: {e}")
        return redirect(url_for('gerenciar_usuarios'))

# ================= RESET DE SENHA =================

@app.route('/resetar-senha', methods=['GET', 'POST'])
@login_required
def resetar_senha():
    """Página para resetar senha"""
    try:
        if current_user.is_admin():
            # Admin pode resetar senha de qualquer usuário
            usuarios = User.query.order_by(User.username).all()
            return render_template('resetar_senha.html', usuarios=usuarios)
        else:
            # Usuário normal só pode resetar própria senha
            return render_template('resetar_senha.html', usuarios=[])
    except Exception as e:
        logger.error(f"Erro ao carregar página de reset de senha: {e}")
        flash('Erro ao carregar página', 'danger')
        return redirect(url_for('index'))

@app.route('/resetar-senha-admin', methods=['POST'])
@login_required
def resetar_senha_admin():
    """Admin reseta senha de outro usuário"""
    # Apenas admins podem usar esta rota
    if not current_user.is_admin():
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    try:
        usuario_id = request.form.get('usuario_id')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if not usuario_id or not nova_senha or not confirmar_senha:
            flash('Preencha todos os campos', 'warning')
            return redirect(url_for('resetar_senha'))
        
        if nova_senha != confirmar_senha:
            flash('As senhas não coincidem', 'warning')
            return redirect(url_for('resetar_senha'))
        
        if len(nova_senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres', 'warning')
            return redirect(url_for('resetar_senha'))
        
        usuario = User.query.get(int(usuario_id))
        if not usuario:
            flash('Usuário não encontrado', 'danger')
            return redirect(url_for('resetar_senha'))
        
        usuario.set_password(nova_senha)
        db.session.commit()
        
        usuario_nome = usuario.jogador.nome if usuario.jogador else usuario.username
        flash(f'Senha do usuário {usuario_nome} atualizada com sucesso!', 'success')
        logger.info(f"Admin {current_user.username} resetou senha do usuário {usuario.username}")
        
        return redirect(url_for('resetar_senha'))
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao resetar senha', 'danger')
        logger.error(f"Erro ao resetar senha admin: {e}")
        return redirect(url_for('resetar_senha'))

@app.route('/resetar-senha-usuario', methods=['POST'])
@login_required
def resetar_senha_usuario():
    """Usuário reseta própria senha"""
    try:
        senha_atual = request.form.get('senha_atual')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if not senha_atual or not nova_senha or not confirmar_senha:
            flash('Preencha todos os campos', 'warning')
            return redirect(url_for('resetar_senha'))
        
        if nova_senha != confirmar_senha:
            flash('As senhas não coincidem', 'warning')
            return redirect(url_for('resetar_senha'))
        
        if len(nova_senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres', 'warning')
            return redirect(url_for('resetar_senha'))
        
        # Verificar senha atual
        if not current_user.check_password(senha_atual):
            flash('Senha atual incorreta', 'danger')
            return redirect(url_for('resetar_senha'))
        
        # Atualizar senha
        current_user.set_password(nova_senha)
        db.session.commit()
        
        flash('Sua senha foi atualizada com sucesso!', 'success')
        logger.info(f"Usuário {current_user.username} alterou própria senha")
        
        return redirect(url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao alterar senha', 'danger')
        logger.error(f"Erro ao alterar senha usuário: {e}")
        return redirect(url_for('resetar_senha'))

# ================= PLACARES =================

@app.route('/placares', methods=['GET', 'POST'])
@login_required
def placares():
    """Página para gerenciar placares dos jogos"""
    
    # Para teste: retornar página simples primeiro
    if request.method == 'GET':
        try:
            # Todos os jogos ordenados por data
            jogos = Jogo.query.order_by(Jogo.data.desc()).all()
            
            # Calcular estatísticas
            estatisticas = calcular_estatisticas_placares()
            
            return render_template('placares_simples.html', 
                                jogos=jogos,
                                estatisticas=estatisticas)
        except Exception as e:
            logger.error(f"Erro ao carregar página de placares: {e}")
            flash('Erro ao carregar página', 'danger')
            # Retornar página de teste em caso de erro
            return render_template('teste_placar.html', jogo_id=1)
    
    if request.method == 'POST':
        # Apenas admins podem registrar placares
        if not current_user.is_admin():
            flash('Apenas administradores podem registrar placares', 'danger')
            return redirect(url_for('placares'))
        try:
            jogo_id = request.form.get('jogo_id')
            placar_associacao = request.form.get('placar_associacao')
            placar_adversario = request.form.get('placar_adversario')
            status = request.form.get('status')
            
            if not jogo_id or not placar_associacao or not placar_adversario:
                flash('Preencha todos os campos obrigatórios', 'warning')
                return redirect(url_for('placares'))
            
            jogo = Jogo.query.get(int(jogo_id))
            if not jogo:
                flash('Jogo não encontrado', 'danger')
                return redirect(url_for('placares'))
            
            # Salvar placar no campo resumo_texto
            placar_texto = f"{placar_associacao} x {placar_adversario} - {status}"
            jogo.resumo_texto = placar_texto
            
            db.session.commit()
            
            flash(f'Placar do jogo {jogo.adversario} registrado com sucesso!', 'success')
            logger.info(f"Placar registrado: {jogo.adversario} {placar_associacao}x{placar_adversario}")
            
            return redirect(url_for('placares'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao registrar placar', 'danger')
            logger.error(f"Erro ao registrar placar: {e}")
            return redirect(url_for('placares'))
    
    # GET - mostrar página
    try:
        # Todos os jogos ordenados por data
        jogos = Jogo.query.order_by(Jogo.data.desc()).all()
        
        # Calcular estatísticas
        estatisticas = calcular_estatisticas_placares()
        
        return render_template('placares.html', 
                            jogos=jogos,
                            estatisticas=estatisticas)
    except Exception as e:
        logger.error(f"Erro ao carregar página de placares: {e}")
        flash('Erro ao carregar página', 'danger')
        return redirect(url_for('index'))

@app.route('/placares/<int:jogo_id>', methods=['GET'])
@login_required
def editar_placar_jogo(jogo_id):
    """Edita placar de um jogo específico"""
    # Apenas admins podem editar placares
    if not current_user.is_admin():
        flash('Apenas administradores podem editar placares', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Todos os jogos ordenados por data
        jogos = Jogo.query.order_by(Jogo.data.desc()).all()
        
        # Calcular estatísticas
        estatisticas = calcular_estatisticas_placares()
        
        return render_template('placares.html', 
                            jogos=jogos,
                            estatisticas=estatisticas,
                            jogo_selecionado=jogo_id)
    except Exception as e:
        logger.error(f"Erro ao carregar jogo para placar: {e}")
        flash('Erro ao carregar jogo', 'danger')
        return redirect(url_for('placares'))

@app.route('/teste-placar/<int:jogo_id>', methods=['GET'])
@login_required
def teste_placar(jogo_id):
    """Rota de teste simples para placar"""
    # Apenas admins podem editar placares
    if not current_user.is_admin():
        flash('Apenas administradores podem editar placares', 'danger')
        return redirect(url_for('index'))
    
    return render_template('teste_placar.html', jogo_id=jogo_id)

@app.route('/editar-placar/<int:jogo_id>', methods=['GET'])
@login_required
def editar_placar_alternativo(jogo_id):
    """Rota alternativa para editar placar (teste)"""
    # Apenas admins podem editar placares
    if not current_user.is_admin():
        flash('Apenas administradores podem editar placares', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Todos os jogos ordenados por data
        jogos = Jogo.query.order_by(Jogo.data.desc()).all()
        
        # Calcular estatísticas
        estatisticas = calcular_estatisticas_placares()
        
        return render_template('placares.html', 
                            jogos=jogos,
                            estatisticas=estatisticas,
                            jogo_selecionado=jogo_id)
    except Exception as e:
        logger.error(f"Erro ao carregar jogo para placar: {e}")
        flash('Erro ao carregar jogo', 'danger')
        return redirect(url_for('placares'))

@app.route('/salvar-placar', methods=['POST'])
@login_required
def salvar_placar():
    """Salva placar do jogo (rota unificada)"""
    # Apenas admins podem salvar placares
    if not current_user.is_admin():
        flash('Apenas administradores podem registrar placares', 'danger')
        return redirect(url_for('index'))
    
    try:
        jogo_id = request.form.get('jogo_id')
        placar_associacao = request.form.get('placar_associacao')
        placar_adversario = request.form.get('placar_adversario')
        status = request.form.get('status')
        
        if not jogo_id or not placar_associacao or not placar_adversario:
            flash('Preencha todos os campos obrigatórios', 'warning')
            return redirect(url_for('placares'))
        
        jogo = Jogo.query.get(int(jogo_id))
        if not jogo:
            flash('Jogo não encontrado', 'danger')
            return redirect(url_for('placares'))
        
        # Salvar placar no campo resumo_texto
        placar_texto = f"{placar_associacao} x {placar_adversario} - {status}"
        jogo.resumo_texto = placar_texto
        
        db.session.commit()
        
        flash(f'Placar do jogo {jogo.adversario} salvo com sucesso!', 'success')
        logger.info(f"Placar salvo: {jogo.adversario} {placar_associacao}x{placar_adversario}")
        
        return redirect(url_for('placares'))
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao salvar placar', 'danger')
        logger.error(f"Erro ao salvar placar: {e}")
        return redirect(url_for('placares'))

def calcular_estatisticas_placares():
    """Calcula estatísticas dos jogos realizados usando resumo_texto"""
    try:
        jogos = Jogo.query.filter(
            Jogo.resumo_texto.isnot(None),
            Jogo.resumo_texto.contains('x')
        ).all()
        
        vitorias = 0
        derrotas = 0
        empates = 0
        
        for jogo in jogos:
            if 'x' in jogo.resumo_texto and 'realizado' in jogo.resumo_texto:
                try:
                    # Extrair placar do texto "3 x 1 - realizado"
                    placar_part = jogo.resumo_texto.split('x')
                    if len(placar_part) >= 2:
                        assoc_gols = int(placar_part[0].strip())
                        adv_gols = int(placar_part[1].split()[0].strip())
                        
                        if assoc_gols > adv_gols:
                            vitorias += 1
                        elif assoc_gols < adv_gols:
                            derrotas += 1
                        else:
                            empates += 1
                except (ValueError, IndexError):
                    continue
        
        total_jogos = vitorias + derrotas + empates
        aproveitamento = (vitorias * 3 + empates) / (total_jogos * 3) * 100 if total_jogos > 0 else 0
        
        return {
            'vitorias': vitorias,
            'derrotas': derrotas,
            'empates': empates,
            'total_jogos': total_jogos,
            'aproveitamento': aproveitamento
        }
    except Exception as e:
        logger.error(f"Erro ao calcular estatísticas: {e}")
        return None

# ================= MIGRATION ROUTE =================

@app.route('/migrate-horario')
def migrate_horario():
    """Rota temporária para migrar a coluna horario"""
    try:
        logger.info("Iniciando migração da coluna horario...")
        
        # Verificar se a coluna já existe
        inspector = db.inspect(db.engine)
        
        # Verificar se a tabela existe
        tables = inspector.get_table_names()
        logger.info(f"Tabelas encontradas: {tables}")
        
        if 'jogo' not in tables:
            logger.info("Tabela 'jogo' não encontrada. Criando todas as tabelas...")
            db.create_all()
            logger.info("Tabelas criadas com sucesso!")
            return "Tabelas criadas com sucesso!"
        
        columns = inspector.get_columns('jogo')
        column_names = [col['name'] for col in columns]
        logger.info(f"Colunas atuais em 'jogo': {column_names}")
        
        if 'horario' not in column_names:
            logger.info("Adicionando coluna 'horario' à tabela jogo...")
            
            # SQL para adicionar a coluna (PostgreSQL)
            if 'postgresql' in str(db.engine.url).lower():
                sql = """
                ALTER TABLE jogo 
                ADD COLUMN horario TIME DEFAULT '19:00:00' NOT NULL;
                """
                logger.info("Usando PostgreSQL para migração")
            else:
                # SQLite (para desenvolvimento local)
                sql = """
                ALTER TABLE jogo 
                ADD COLUMN horario TEXT DEFAULT '19:00:00' NOT NULL;
                """
                logger.info("Usando SQLite para migração")
            
            db.session.execute(sql)
            db.session.commit()
            
            logger.info("Coluna 'horario' adicionada com sucesso!")
            
            # Verificar novamente
            columns = inspector.get_columns('jogo')
            column_names = [col['name'] for col in columns]
            
            return f"Coluna 'horario' adicionada com sucesso! Colunas: {column_names}"
            
        else:
            logger.info("Coluna 'horario' já existe na tabela jogo")
            return "Coluna 'horario' já existe na tabela jogo"
            
    except Exception as e:
        logger.error(f"Erro na migração: {e}")
        db.session.rollback()
        return f"Erro na migração: {e}"

@app.route('/debug-info')
def debug_info():
    """Rota para debug de informações do sistema"""
    try:
        info = {
            'database_url': str(db.engine.url).replace('password', '***'),
            'tables': [],
            'jogo_columns': []
        }
        
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        info['tables'] = tables
        
        if 'jogo' in tables:
            columns = inspector.get_columns('jogo')
            info['jogo_columns'] = [col['name'] for col in columns]
        
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)})

# ================= WHATSAPP GRUPOS =================

@app.route('/whatsapp/grupo', methods=['GET', 'POST'])
@login_required
def whatsapp_grupo():
    """Página para criar mensagens para grupos do WhatsApp"""
    try:
        # Forçar refresh do banco para garantir dados atualizados
        forcar_refresh_banco()
        
        # Buscar jogos para seleção
        jogos = Jogo.query.order_by(Jogo.data.desc()).all()
        
        mensagem_grupo = None  # Inicializar variável
        
        if request.method == 'POST':
            tipo_mensagem = request.form.get('tipo_mensagem')
            mensagem_personalizada = request.form.get('mensagem_personalizada', '').strip()
            jogo_id = request.form.get('jogo_id')
            
            # Debug do formulário
            logger.info(f"Formulário POST recebido para grupo:")
            logger.info(f"  - tipo_mensagem: '{tipo_mensagem}'")
            logger.info(f"  - mensagem_personalizada: '{mensagem_personalizada}'")
            logger.info(f"  - jogo_id: '{jogo_id}'")
            
            # Processar based on tipo
            if tipo_mensagem == 'jogo':
                jogo = Jogo.query.get(jogo_id) if jogo_id else None
                
                if jogo:
                    mensagem_grupo = f"""
⚽ CONVOCAÇÃO DE JOGO

📅 Data: {jogo.data.strftime('%d/%m/%Y')}
⏰ Horário: {jogo.horario.strftime('%H:%M') if jogo.horario else '19:00'}
📍 Local: {jogo.local or 'Campo da UFPA'}
🆚 Adversário: {jogo.adversario}

👥 Todos os jogadores estão convidados!
Por favor, confirmem presença no app.

📲 Acesse: https://associacao-ced4.onrender.com/presencas/{jogo.id}

Contamos com todos! 💪
"""
                    flash('Mensagem de jogo gerada com sucesso!', 'success')
                else:
                    flash('Selecione um jogo válido', 'warning')
                    return redirect(url_for('whatsapp_grupo'))
                    
            elif tipo_mensagem == 'customizada':
                if mensagem_personalizada and len(mensagem_personalizada.strip()) > 0:
                    mensagem_grupo = mensagem_personalizada.strip()
                    flash('Mensagem personalizada gerada com sucesso!', 'success')
                else:
                    flash('Digite uma mensagem personalizada valida', 'warning')
                    return redirect(url_for('whatsapp_grupo'))
                    
            else:  # mensagem padrão
                mensagem_grupo = f"""
📢 COMUNICADO IMPORTANTE

Olá, grupo!

📅 Próximos eventos:
- Fiquem atentos às convocações
- Participem ativamente dos jogos
- Contribuam com o crescimento da associação

💡 Dúvidas ou sugestões?
Entre em contato com a administração.

📲 Acessem o app: https://associacao-ced4.onrender.com

Atenciosamente,
Diretoria da Associação UFPA
"""
                flash('Mensagem padrao gerada com sucesso!', 'success')
        
        # Codificar mensagem para URL
        mensagem_codificada = quote(mensagem_grupo.strip()) if mensagem_grupo and mensagem_grupo.strip() else None
        
        return render_template('whatsapp_grupo.html',
                             jogos=jogos,
                             mensagem_grupo=mensagem_codificada)
        
    except Exception as e:
        logger.error(f"Erro ao preparar WhatsApp para grupo: {e}")
        flash('Erro ao preparar envio de WhatsApp', 'danger')
        return redirect(url_for('index'))

# ================= FIM WHATSAPP GRUPOS =================

if __name__ == '__main__':
    print("Iniciando servidor Flask...")
    
    with app.app_context():
        # Verificar se o arquivo do banco existe
        import os
        db_file = "associacao.db"
        if not os.path.exists(db_file):
            print(f"Criando arquivo do banco: {db_file}")
        
        # Criar todas as tabelas se não existirem
        try:
            db.create_all()
            print(f"Banco de dados criado/verificado: {db_file}")
        except Exception as e:
            print(f"Erro ao criar banco: {e}")
            exit(1)
        
        # Verificar e adicionar colunas faltantes
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            
            # Verificar colunas na tabela financeiro
            financeiro_columns = [col['name'] for col in inspector.get_columns('financeiro')]
            
            if 'jogador_id' not in financeiro_columns:
                print("Adicionando coluna jogador_id...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN jogador_id INTEGER'))
                db.session.commit()
            
            if 'mes_referencia' not in financeiro_columns:
                print("Adicionando coluna mes_referencia...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN mes_referencia VARCHAR(20)'))
                db.session.commit()
            
            if 'ano_referencia' not in financeiro_columns:
                print("Adicionando coluna ano_referencia...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN ano_referencia INTEGER'))
                db.session.commit()
                
            # Verificar colunas na tabela jogador
            jogador_columns = [col['name'] for col in inspector.get_columns('jogador')]
            
            if 'ativo' not in jogador_columns:
                print("Adicionando coluna ativo à tabela jogador...")
                db.session.execute(text('ALTER TABLE jogador ADD COLUMN ativo BOOLEAN DEFAULT 1'))
                db.session.commit()
            
            if 'nativo' not in jogador_columns:
                print("Adicionando coluna nativo à tabela jogador...")
                db.session.execute(text('ALTER TABLE jogador ADD COLUMN nativo BOOLEAN DEFAULT 0'))
                db.session.commit()
            
            # Verificar colunas na tabela jogo
            jogo_columns = [col['name'] for col in inspector.get_columns('jogo')]
            
            if 'horario' not in jogo_columns:
                print("Adicionando coluna horario à tabela jogo...")
                db.session.execute(text('ALTER TABLE jogo ADD COLUMN horario TIME DEFAULT "19:00:00"'))
                db.session.commit()
                
        except Exception as e:
            logger.warning(f"Aviso ao verificar colunas: {e}")
        
        print("Banco de dados inicializado com sucesso!")
        print("Servidor disponível em: http://localhost:5000")
        print("WhatsApp Grupo: http://localhost:5000/whatsapp/grupo")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
