# Solução para o Erro: "no such column: financeiro.jogador_id"

## Problema
O erro ocorre porque o SQLAlchemy está tentando acessar colunas que ainda não existem no banco de dados, ou o servidor Flask precisa ser reiniciado após as mudanças no modelo.

## Solução Aplicada

### 1. Script de Migração Executado
O script `fix_database.py` foi executado e confirmou que as colunas já existem:
- ✅ `jogador_id`
- ✅ `mes_referencia`
- ✅ `ano_referencia`

### 2. Verificação Automática Adicionada
O arquivo `app.py` foi atualizado para verificar e criar as colunas automaticamente na inicialização.

## Como Resolver

### Opção 1: Reiniciar o Servidor Flask
Se o servidor Flask estiver rodando, **pare e reinicie**:

1. Pare o servidor (Ctrl+C no terminal)
2. Execute novamente:
   ```bash
   python app.py
   ```

### Opção 2: Executar Script de Migração Manualmente
Se ainda houver problemas, execute:

```bash
python fix_database.py
```

### Opção 3: Recriar o Banco de Dados (CUIDADO: Apaga dados)
Se nada funcionar e você não tiver dados importantes:

```python
from app import app, db
with app.app_context():
    db.drop_all()
    db.create_all()
```

## Verificação

Para verificar se as colunas existem:

```bash
python fix_database.py
```

Você deve ver:
```
Colunas existentes: ['id', 'data', 'tipo', 'descricao', 'valor', 'jogador_id', 'mes_referencia', 'ano_referencia']
```

## Próximos Passos

1. **Reinicie o servidor Flask** se ainda estiver rodando
2. Acesse a página de Mensalidades
3. O sistema deve funcionar normalmente

## Nota Importante

Se você tem mensalidades antigas no banco (criadas antes da migração), elas podem não aparecer na nova visualização porque não têm os campos `jogador_id`, `mes_referencia` e `ano_referencia` preenchidos. Elas continuarão funcionando no sistema financeiro geral, mas não aparecerão na tabela de mensalidades por sócio.
