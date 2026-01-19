"""
Script para limpar automaticamente o banco de dados, mantendo apenas o usuário admin
"""

from app import app, db, User, Jogador, Financeiro, Jogo, Participacao

def limpar_banco():
    """Limpa todas as tabelas exceto usuário admin"""
    with app.app_context():
        print("Iniciando limpeza do banco de dados...")
        
        try:
            # Limpar tabelas em ordem correta (respeitando foreign keys)
            print("Apagando participacoes...")
            Participacao.query.delete()
            
            print("Apagando jogos...")
            Jogo.query.delete()
            
            print("Apagando registros financeiros...")
            Financeiro.query.delete()
            
            print("Apagando jogadores...")
            Jogador.query.delete()
            
            print("Apagando usuários (exceto admin)...")
            User.query.filter(User.username != 'admin').delete()
            
            # Commit das alterações
            db.session.commit()
            
            print("Banco de dados limpo com sucesso!")
            print("Usuário admin mantido.")
            print("Outros usuários, jogadores, jogos, participacoes e registros financeiros foram removidos.")
            
        except Exception as e:
            print(f"Erro durante a limpeza: {e}")
            db.session.rollback()
            print("Operação desfeita. Nenhum dado foi alterado.")

if __name__ == '__main__':
    limpar_banco()
