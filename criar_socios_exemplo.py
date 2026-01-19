#!/usr/bin/env python3
"""
Script para criar sócios de exemplo para testar cadastro de senhas
"""

from app import app, db, Jogador

def criar_socios_exemplo():
    """Cria sócios de exemplo sem usuários"""
    with app.app_context():
        # Criar alguns sócios de exemplo
        socios_exemplo = [
            {
                'nome': 'João Silva',
                'telefone': '(11) 98765-4321',
                'tipo': 'SOCIO',
                'ativo': True,
                'nativo': False
            },
            {
                'nome': 'Maria Santos',
                'telefone': '(11) 91234-5678',
                'tipo': 'SOCIO',
                'ativo': True,
                'nativo': True
            },
            {
                'nome': 'Pedro Oliveira',
                'telefone': '(11) 99876-5432',
                'tipo': 'SOCIO',
                'ativo': True,
                'nativo': False
            },
            {
                'nome': 'Ana Costa',
                'telefone': '(11) 97654-3210',
                'tipo': 'SOCIO',
                'ativo': False,
                'nativo': False
            }
        ]
        
        criados = 0
        for socio_data in socios_exemplo:
            # Verificar se já existe
            existente = Jogador.query.filter_by(nome=socio_data['nome']).first()
            if existente:
                print(f"Socio '{socio_data['nome']}' ja existe")
                continue
            
            # Criar novo sócio
            novo_socio = Jogador(**socio_data)
            db.session.add(novo_socio)
            criados += 1
            print(f"Criado socio: {socio_data['nome']}")
        
        db.session.commit()
        print(f"\nTotal de socios criados: {criados}")
        print("\nAgora voce pode testar o cadastro de senhas!")
        print("1. Acesse: http://localhost:5000/cadastrar-senha-socio")
        print("2. Como admin, crie senhas para os socios")
        print("3. Como socio, cadastre sua propria senha")

if __name__ == '__main__':
    criar_socios_exemplo()
