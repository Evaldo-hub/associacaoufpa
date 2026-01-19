"""
Script de migração para adicionar campos de mensalidade ao modelo Financeiro
Execute este script uma vez para atualizar o banco de dados existente
"""

from app import app, db, Financeiro
from sqlalchemy import text

def migrate_database():
    """Adiciona os novos campos ao banco de dados"""
    with app.app_context():
        try:
            # Verificar se as colunas já existem
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('financeiro')]
            
            if 'jogador_id' not in columns:
                print("Adicionando coluna jogador_id...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN jogador_id INTEGER'))
                db.session.commit()
                print("[OK] Coluna jogador_id adicionada")
            else:
                print("[INFO] Coluna jogador_id ja existe")
            
            if 'mes_referencia' not in columns:
                print("Adicionando coluna mes_referencia...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN mes_referencia VARCHAR(20)'))
                db.session.commit()
                print("[OK] Coluna mes_referencia adicionada")
            else:
                print("[INFO] Coluna mes_referencia ja existe")
            
            if 'ano_referencia' not in columns:
                print("Adicionando coluna ano_referencia...")
                db.session.execute(text('ALTER TABLE financeiro ADD COLUMN ano_referencia INTEGER'))
                db.session.commit()
                print("[OK] Coluna ano_referencia adicionada")
            else:
                print("[INFO] Coluna ano_referencia ja existe")
            
            # Tentar criar índice se não existir
            try:
                db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_financeiro_jogador_id ON financeiro(jogador_id)'))
                db.session.commit()
                print("[OK] Indice criado")
            except Exception as e:
                print(f"[INFO] Indice ja existe ou erro: {e}")
            
            print("\n[OK] Migracao concluida com sucesso!")
            print("[AVISO] Mensalidades antigas podem nao ter os campos preenchidos.")
            print("        Elas continuarao funcionando, mas nao aparecerao na nova visualizacao.")
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERRO] Erro na migracao: {e}")
            raise

if __name__ == '__main__':
    print("Iniciando migracao do banco de dados...")
    print("=" * 50)
    migrate_database()
    print("=" * 50)
    print("Processo concluido!")
