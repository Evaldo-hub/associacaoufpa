"""
Script para corrigir o banco de dados adicionando as colunas necessárias
"""

import sqlite3
import os

def fix_database():
    """Adiciona as colunas necessárias ao banco de dados"""
    db_path = 'instance/associacao.db'
    
    if not os.path.exists(db_path):
        print(f"[ERRO] Banco de dados nao encontrado em: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar colunas existentes
        cursor.execute("PRAGMA table_info(financeiro)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Colunas existentes: {columns}")
        
        # Adicionar colunas se não existirem
        if 'jogador_id' not in columns:
            print("Adicionando jogador_id...")
            cursor.execute("ALTER TABLE financeiro ADD COLUMN jogador_id INTEGER")
            conn.commit()
            print("[OK] jogador_id adicionada")
        else:
            print("[INFO] jogador_id ja existe")
        
        if 'mes_referencia' not in columns:
            print("Adicionando mes_referencia...")
            cursor.execute("ALTER TABLE financeiro ADD COLUMN mes_referencia VARCHAR(20)")
            conn.commit()
            print("[OK] mes_referencia adicionada")
        else:
            print("[INFO] mes_referencia ja existe")
        
        if 'ano_referencia' not in columns:
            print("Adicionando ano_referencia...")
            cursor.execute("ALTER TABLE financeiro ADD COLUMN ano_referencia INTEGER")
            conn.commit()
            print("[OK] ano_referencia adicionada")
        else:
            print("[INFO] ano_referencia ja existe")
        
        # Criar índice
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_financeiro_jogador_id ON financeiro(jogador_id)")
            conn.commit()
            print("[OK] Indice criado")
        except Exception as e:
            print(f"[INFO] Erro ao criar indice: {e}")
        
        # Verificar novamente
        cursor.execute("PRAGMA table_info(financeiro)")
        columns_final = [row[1] for row in cursor.fetchall()]
        print(f"\nColunas finais: {columns_final}")
        
        conn.close()
        print("\n[OK] Banco de dados corrigido com sucesso!")
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro ao corrigir banco: {e}")
        return False

if __name__ == '__main__':
    print("Corrigindo banco de dados...")
    print("=" * 50)
    fix_database()
    print("=" * 50)
