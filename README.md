# Sistema de Gestão de Associação Esportiva

Sistema web para gerenciamento de associação esportiva desenvolvido com Flask, incluindo controle de jogadores, jogos, presenças, pagamentos e finanças.

## 🚀 Funcionalidades

- **Dashboard Financeiro**: Visão geral do saldo, mensalidades, partidas e despesas
- **Gestão de Jogadores**: Cadastro de sócios e convidados
- **Controle de Jogos**: Cadastro de jogos com adversário, local e data
- **Presenças e Pagamentos**: Controle de presenças e pagamentos por partida
- **Resumo Técnico**: Registro de gols, expulsões e craque da partida
- **Mensalidades**: Lançamento de mensalidades dos sócios
- **Extrato Financeiro**: Visualização completa das movimentações financeiras

## 📋 Requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

## 🔧 Instalação

1. Clone ou baixe o repositório
2. Instale as dependências:

```bash
pip install -r requirements.txt
```

## ▶️ Executando

Execute o aplicativo:

```bash
python app.py
```

O sistema estará disponível em: `http://localhost:5000`

## 📁 Estrutura do Projeto

```
AssociacaoUFPA/
├── app.py                 # Aplicação principal Flask
├── requirements.txt        # Dependências do projeto
├── README.md              # Este arquivo
├── templates/             # Templates HTML
│   ├── base.html
│   ├── index.html
│   ├── jogos.html
│   ├── presencas.html
│   ├── resumo_jogo.html
│   ├── jogadores.html
│   ├── associados.html
│   └── financeiro.html
└── instance/              # Banco de dados SQLite
    └── associacao.db
```

## 🔐 Segurança

⚠️ **IMPORTANTE**: Para produção, altere a `SECRET_KEY` no arquivo `app.py`:

```python
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua-chave-secreta-aqui')
```

Ou defina a variável de ambiente:
```bash
export SECRET_KEY='sua-chave-secreta-aqui'
```

## 🗄️ Banco de Dados

O sistema utiliza SQLite por padrão. O banco de dados é criado automaticamente na primeira execução.

### Modelos de Dados

- **Jogador**: Informações dos jogadores (sócios e convidados)
- **Jogo**: Dados dos jogos realizados
- **Participacao**: Relaciona jogadores com jogos (presenças, pagamentos, estatísticas)
- **Financeiro**: Movimentações financeiras (mensalidades, partidas, despesas)

## 🛠️ Melhorias Implementadas

- ✅ Validação de entrada de dados
- ✅ Tratamento de erros robusto
- ✅ Sistema de logging
- ✅ Templates HTML separados
- ✅ Mensagens de feedback ao usuário
- ✅ Índices no banco de dados para melhor performance
- ✅ Prevenção de duplicatas
- ✅ Interface responsiva com Bootstrap 5

## 📝 Uso

1. **Cadastrar Jogadores**: Acesse "Atletas" e cadastre os jogadores
2. **Criar Jogo**: Vá em "Jogos" e cadastre um novo jogo
3. **Registrar Presenças**: Clique em "Presenças/Pagos" no jogo e marque quem confirmou e pagou
4. **Resumo Técnico**: Acesse "Resumo Técnico" para registrar gols e expulsões
5. **Mensalidades**: Use "Mensalidades" para lançar pagamentos mensais
6. **Financeiro**: Visualize todas as movimentações em "Caixa"

## 🐛 Solução de Problemas

- Se o banco de dados não for criado, execute manualmente:
  ```python
  from app import app, db
  with app.app_context():
      db.create_all()
  ```

- Para limpar o banco de dados (CUIDADO: apaga todos os dados):
  ```python
  from app import app, db
  with app.app_context():
      db.drop_all()
      db.create_all()
  ```

## 📄 Licença

Este projeto é de uso interno da associação.

## 👨‍💻 Desenvolvimento

Para contribuir ou reportar problemas, verifique os logs no console durante a execução do aplicativo.
