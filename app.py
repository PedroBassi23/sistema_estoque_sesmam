import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
import csv
import io

# --- CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)

# Chave secreta: Em produção, virá de uma variável de ambiente.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-padrao-para-desenvolvimento')

# Caminho do banco de dados: Configurável para deploy.
# No Render, vamos criar um "Disco Persistente" e apontar para ele.
DATABASE_DIR = os.environ.get('DATABASE_DIR', os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(DATABASE_DIR, 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELOS DO BANCO DE DADOS (Sem alterações) ---
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    categoria = db.Column(db.String(50), nullable=False)
    contrato = db.Column(db.String(100), nullable=True) # NOVO CAMPO
    unidade = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    valor_unitario = db.Column(db.Float, default=0.0)
    estoque_minimo = db.Column(db.Integer, default=0)
    movimentacoes = db.relationship('Movimentacao', backref='produto', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Produto {self.nome}>'

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    responsavel = db.Column(db.String(100))
    observacao = db.Column(db.String(200))

    def __repr__(self):
        return f'<Movimentacao {self.id}>'

# --- SISTEMA DE LOGIN SIMPLES ---
USUARIOS = {"admin": "admin"}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USUARIOS and USUARIOS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

# --- ROTAS PRINCIPAIS (Sem alterações na lógica) ---
@app.route('/')
@login_required
def dashboard():
    total_itens = db.session.query(Produto.id).count()
    total_produtos = db.session.query(db.func.sum(Produto.quantidade)).scalar() or 0
    valor_total_estoque = db.session.query(db.func.sum(Produto.quantidade * Produto.valor_unitario)).scalar() or 0.0
    produtos_estoque_baixo = Produto.query.filter(Produto.quantidade <= Produto.estoque_minimo, Produto.estoque_minimo > 0).all()

    stats = {
        'total_itens': total_itens,
        'total_produtos': int(total_produtos),
        'valor_total_estoque': f'{valor_total_estoque:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    }
    return render_template('dashboard.html', stats=stats, produtos_estoque_baixo=produtos_estoque_baixo)

@app.route('/estoque', methods=['GET', 'POST'])
@login_required
def estoque():
    if request.method == 'POST':
        nome = request.form['nome']
        produto_existente = Produto.query.filter_by(nome=nome).first()
        if produto_existente:
            flash(f'O item "{nome}" já existe no estoque.', 'danger')
        else:
            novo_produto = Produto(
                nome=nome,
                categoria=request.form['categoria'],
                contrato=request.form.get('contrato', ''),
                unidade=request.form['unidade'],
                quantidade=int(request.form.get('quantidade', 0)),
                valor_unitario=float(request.form.get('valor_unitario', 0.0).replace(',', '.')),
                estoque_minimo=int(request.form.get('estoque_minimo', 0))
            )
            db.session.add(novo_produto)
            db.session.commit()
            flash(f'Item "{nome}" adicionado com sucesso!', 'success')
        return redirect(url_for('estoque'))

    filtro_nome = request.args.get('filtro_nome', '')
    filtro_categoria = request.args.get('filtro_categoria', '')
    filtro_contrato = request.args.get('filtro_contrato', '')
    
    query = Produto.query
    if filtro_nome: query = query.filter(Produto.nome.ilike(f'%{filtro_nome}%'))
    if filtro_categoria: query = query.filter(Produto.categoria.ilike(f'%{filtro_categoria}%'))
    if filtro_contrato: query = query.filter(Produto.contrato.ilike(f'%{filtro_contrato}%'))

    produtos = query.order_by(Produto.nome).all()
    categorias = sorted(list(set([p.categoria for p in Produto.query.all()])))
    contratos = sorted(list(set([p.contrato for p in Produto.query.filter(Produto.contrato != None, Produto.contrato != '').all()])))

    return render_template('estoque.html', produtos=produtos, categorias=categorias, contratos=contratos, filtro_nome=filtro_nome, filtro_categoria=filtro_categoria, filtro_contrato=filtro_contrato)

@app.route('/estoque/editar/<int:id>', methods=['POST'])
@login_required
def editar_produto(id):
    produto = Produto.query.get_or_404(id)
    novo_nome = request.form['nome']
    if produto.nome != novo_nome and Produto.query.filter_by(nome=novo_nome).first():
        flash(f'O nome de item "{novo_nome}" já existe.', 'danger')
        return redirect(url_for('estoque'))
        
    produto.nome = novo_nome
    produto.categoria = request.form['categoria']
    produto.contrato = request.form.get('contrato', '')
    produto.unidade = request.form['unidade']
    produto.valor_unitario = float(request.form.get('valor_unitario', '0').replace(',', '.'))
    produto.estoque_minimo = int(request.form.get('estoque_minimo', '0'))
    db.session.commit()
    flash(f'Produto "{produto.nome}" atualizado com sucesso!', 'success')
    return redirect(url_for('estoque'))

@app.route('/estoque/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    flash(f'Produto "{produto.nome}" e suas movimentações foram excluídos.', 'success')
    return redirect(url_for('estoque'))

@app.route('/movimentacoes', methods=['GET', 'POST'])
@login_required
def movimentacoes():
    if request.method == 'POST':
        produto_id = request.form['produto_id']
        tipo = request.form['tipo']
        quantidade = int(request.form['quantidade'])
        produto = Produto.query.get(produto_id)

        if tipo == 'Saída' and produto.quantidade < quantidade:
            flash(f'Estoque insuficiente para "{produto.nome}".', 'warning')
            return redirect(url_for('movimentacoes'))
        
        produto.quantidade += quantidade if tipo == 'Entrada' else -quantidade
        
        nova_movimentacao = Movimentacao(
            produto_id=produto_id, tipo=tipo, quantidade=quantidade,
            responsavel=request.form['responsavel'], observacao=request.form['observacao']
        )
        db.session.add(nova_movimentacao)
        db.session.commit()
        flash(f'Movimentação de {tipo} registrada com sucesso para "{produto.nome}"!', 'success')
        
        if produto.estoque_minimo > 0 and produto.quantidade <= produto.estoque_minimo:
            flash(f'Atenção: O estoque de "{produto.nome}" está baixo.', 'warning')
        return redirect(url_for('movimentacoes'))

    produtos = Produto.query.order_by(Produto.nome).all()
    ultimas_movimentacoes = Movimentacao.query.order_by(Movimentacao.data.desc()).limit(10).all()
    return render_template('movimentacoes.html', produtos=produtos, movimentacoes=ultimas_movimentacoes)

@app.route('/relatorios')
@login_required
def relatorios():
    query = Movimentacao.query.order_by(Movimentacao.data.desc())
    
    # Filtros
    filtro_produto = request.args.get('filtro_produto')
    filtro_tipo = request.args.get('filtro_tipo')
    filtro_data_inicio = request.args.get('filtro_data_inicio')
    filtro_data_fim = request.args.get('filtro_data_fim')

    if filtro_produto:
        query = query.filter(Movimentacao.produto_id == filtro_produto)
    if filtro_tipo:
        query = query.filter(Movimentacao.tipo == filtro_tipo)
    if filtro_data_inicio:
        query = query.filter(Movimentacao.data >= datetime.strptime(filtro_data_inicio, '%Y-%m-%d'))
    if filtro_data_fim:
        data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Movimentacao.data < data_fim)

    movimentacoes = query.all()
    produtos = Produto.query.order_by(Produto.nome).all()
    
    return render_template('relatorios.html', 
        movimentacoes=movimentacoes, 
        produtos=produtos,
        filtro_produto=filtro_produto,
        filtro_tipo=filtro_tipo,
        filtro_data_inicio=filtro_data_inicio,
        filtro_data_fim=filtro_data_fim)

@app.route('/exportar_csv')
@login_required
def exportar_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nome', 'Categoria', 'Contrato', 'Qtd. em Estoque', 'Estoque Mínimo', 'Valor Unitário (R$)', 'Valor Total (R$)'])
    
    for produto in Produto.query.all():
        writer.writerow([
            produto.id, produto.nome, produto.categoria, produto.contrato,
            produto.quantidade, produto.estoque_minimo,
            f'{produto.valor_unitario:.2f}'.replace('.', ','),
            f'{(produto.quantidade * produto.valor_unitario):.2f}'.replace('.', ',')
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=estoque_{datetime.now().strftime("%Y-%m-%d")}.csv'
    response.headers['Content-type'] = 'text/csv; charset=utf-8'
    return response

@app.route('/api/chart_data')
@login_required
def chart_data():
    hoje = datetime.utcnow().date()
    dias = [hoje - timedelta(days=i) for i in range(29, -1, -1)]
    labels = [dia.strftime('%d/m') for dia in dias]
    dados = {label: {'entradas': 0, 'saidas': 0} for label in labels}
    
    data_inicio_query = hoje - timedelta(days=29)
    movimentacoes = Movimentacao.query.filter(db.func.date(Movimentacao.data) >= data_inicio_query).all()
    
    for mov in movimentacoes:
        chave_data = mov.data.strftime('%d/%m')
        if mov.tipo == 'Entrada':
            dados[chave_data]['entradas'] += mov.quantidade
        else:
            dados[chave_data]['saidas'] += mov.quantidade
            
    return jsonify(labels=labels, entradas=[d['entradas'] for d in dados.values()], saidas=[d['saidas'] for d in dados.values()])

# Garante que o banco de dados seja criado se não existir
with app.app_context():
    if not os.path.exists(DATABASE_PATH):
        print(f"Criando banco de dados em: {DATABASE_PATH}")
        db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

