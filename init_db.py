#!/usr/bin/env python3
"""
Script para inicializar o banco de dados com usuários padrão
"""

from app import app, db, User, Jogador
from datetime import datetime

def init_database():
    """Inicializa o banco de dados com dados básicos"""
    with app.app_context():
        # Criar todas as tabelas
        db.create_all()
        
        # Verificar se já existe usuário admin
        admin_user = User.query.filter_by(username='admin').first()
        
        if not admin_user:
            # Criar usuário admin
            admin = User(
                username='admin',
                email='admin@associacao.com',
                role='admin',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Criar um jogador associado ao admin (opcional)
            jogador_admin = Jogador(
                nome='Administrador',
                telefone='(00) 00000-0000',
                tipo='SOCIO',
                ativo=True,
                nativo=True
            )
            db.session.add(jogador_admin)
            db.session.flush()  # Para obter o ID do jogador
            
            admin.jogador_id = jogador_admin.id
            
            print("Usuario admin criado:")
            print("   Usuario: admin")
            print("   Senha: admin123")
            print("   Email: admin@associacao.com")
        else:
            print("Info: Usuario admin ja existe")
        
        # Criar usuário jogador exemplo
        jogador_user = User.query.filter_by(username='jogador1').first()
        
        if not jogador_user:
            # Criar jogador exemplo
            jogador_exemplo = Jogador(
                nome='Jogador Exemplo',
                telefone='(11) 98765-4321',
                tipo='SOCIO',
                ativo=True,
                nativo=False
            )
            db.session.add(jogador_exemplo)
            db.session.flush()  # Para obter o ID do jogador
            
            # Criar usuário para o jogador
            user_jogador = User(
                username='jogador1',
                email='jogador1@associacao.com',
                role='jogador',
                jogador_id=jogador_exemplo.id,
                is_active=True
            )
            user_jogador.set_password('jogador123')
            db.session.add(user_jogador)
            
            print("Usuario jogador criado:")
            print("   Usuario: jogador1")
            print("   Senha: jogador123")
            print("   Email: jogador1@associacao.com")
        else:
            print("Info: Usuario jogador1 ja existe")
        
        # Commit das alterações
        db.session.commit()
        print("Banco de dados inicializado com sucesso!")

if __name__ == '__main__':
    init_database()
