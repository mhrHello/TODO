from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory # flash を追加
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user # Flask-Login 関連を追加
from flask_bcrypt import Bcrypt # Bcrypt を追加
import os
from datetime import date, timedelta, datetime
# アプリケーションの初期化
app = Flask(__name__)

# ★追加：シークレットキーの設定 (本番環境ではもっと複雑なキーにしてください)
app.config['SECRET_KEY'] = '4bcec385ac09f1ff296059e6bf48e1e727a4446cb1ec0fe9' # ここをユニークな文字列に変更してください

# データベース設定
# SQLiteを使うローカル開発用
basedir = os.path.abspath(os.path.dirname(__file__))
sqlite_uri = 'postgresql://todo_db_bnxt_user:RLfDyZhLN4KH6QXkNWH1fIPPtjviSJar@dpg-d1h9foali9vc73bgs3ig-a.singapore-postgres.render.com/todo_db_bnxt' + os.path.join(basedir, 'site.db')


# Renderなどの本番環境では環境変数からDATABASE_URLを読み込む
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', sqlite_uri)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app) # ★追加：Bcrypt の初期化

# ★追加：Flask-Login の初期化
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # ログインしていないユーザーが @login_required のページにアクセスした際のリダイレクト先

# データベースモデルの定義

# ★追加：User モデルの定義
class User(db.Model, UserMixin): # UserMixin を継承する
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False) # ハッシュ化されたパスワードを保存

    def __repr__(self):
        return f"User('{self.username}')"
# Flask-Login がユーザーをロードするためのコールバック関数
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.template_filter('to_datetime')
def to_datetime_filter(s):
    # sがdatetime.dateオブジェクトであればそのまま返す
    if isinstance(s, date):
        return s
    # 文字列であれば解析
    return datetime.strptime(s, '%Y-%m-%d').date()

# TODO項目
class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)
    task = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pending')
    description = db.Column(db.Text, nullable=True)
    
    # ★追加：ユーザーID
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # user モデルとのリレーションシップを定義 (オプションだが便利)
    user = db.relationship('User', backref='todos', lazy=True)

    def __repr__(self):
        return f'<Todo {self.task}>'

# 日記項目
class Diary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False) # unique=True は削除（ユーザーごとにユニークであればOK）
    content = db.Column(db.Text, nullable=False)

    # ★追加：ユーザーID
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # user モデルとのリレーションシップを定義 (オプションだが便利)
    user = db.relationship('User', backref='diaries', lazy=True)

    def __repr__(self):
        return f'<Diary {self.date}>'

# データベースの初期化（初回のみ実行）
# User モデルを追加したので、既存の site.db を削除して再作成するか、
# Pythonインタプリタで `from app import db; db.create_all()` を実行してテーブルを追加する必要があります。
with app.app_context():
    db.create_all()

@app.route('/favicon.ico')
def favicon():
    # staticフォルダにfavicon.icoがある場合
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# ★変更：既存のルートに @login_required を追加
@app.route('/')
@login_required # ログインが必須となる
def index():
    from datetime import date
    today_str = date.today().isoformat()
    return redirect(url_for('show_day', selected_date=today_str))
@app.route('/<selected_date>')
@login_required
def show_day(selected_date):
    # ★変更：current_user.id でフィルタリング
    todos = Todo.query.filter_by(date=selected_date, user_id=current_user.id).order_by(Todo.id).all()
    diary = Diary.query.filter_by(date=selected_date, user_id=current_user.id).first()

    current_date_obj = date.fromisoformat(selected_date)
    prev_date = (current_date_obj - timedelta(days=1)).isoformat()
    next_date = (current_date_obj + timedelta(days=1)).isoformat()

    return render_template('index.html',
                           selected_date=selected_date,
                           todos=todos,
                           diary=diary,
                           prev_date=prev_date,
                           next_date=next_date)

@app.route('/add_todo/<selected_date>', methods=['POST'])
@login_required
def add_todo(selected_date):
    task = request.form['task']
    # ★変更：user_id を指定してTODOを作成
    new_todo = Todo(date=selected_date, task=task, user_id=current_user.id)
    db.session.add(new_todo)
    db.session.commit()
    return redirect(url_for('show_day', selected_date=selected_date))

# TODOの更新・削除、日記の更新も同様に、
# まず対象のTODO/日記を current_user.id でフィルタリングして取得し、
# その後、そのデータが本当に現在のユーザーのものであるかを確認するロジックを追加します。
# 例:
@app.route('/update_todo_status/<int:todo_id>', methods=['POST'])
@login_required
def update_todo_status(todo_id):
    # ★変更：user_id でフィルタリングして取得
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    todo.status = request.form['status']
    db.session.commit()
    return redirect(url_for('show_day', selected_date=todo.date))

# TODO詳細更新 (顛末)
@app.route('/update_todo_description/<int:todo_id>', methods=['POST'])
@login_required
def update_todo_description(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    todo.description = request.form['description']
    db.session.commit()
    return redirect(url_for('show_day', selected_date=todo.date))

# TODO削除
@app.route('/delete_todo/<int:todo_id>', methods=['POST'])
@login_required
def delete_todo(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    selected_date = todo.date # リダイレクト用に日付を取得
    db.session.delete(todo)
    db.session.commit()
    return redirect(url_for('show_day', selected_date=selected_date))

# 日記更新 (新規作成も含む)
@app.route('/update_diary/<selected_date>', methods=['POST'])
@login_required
def update_diary(selected_date):
    content = request.form['content']
    diary = Diary.query.filter_by(date=selected_date, user_id=current_user.id).first()
    if diary:
        diary.content = content
    else:
        new_diary = Diary(date=selected_date, content=content, user_id=current_user.id)
        db.session.add(new_diary)
    db.session.commit()
    flash('日記を保存しました！', 'success')
    return redirect(url_for('show_day', selected_date=selected_date))

@app.route('/copy_yesterday_todos/<selected_date>', methods=['POST'])
@login_required
def copy_yesterday_todos(selected_date):
    # 1. 今日の日付のオブジェクトを作成
    current_date_obj = date.fromisoformat(selected_date)

    # 2. 昨日の日付を計算
    yesterday_date_obj = current_date_obj - timedelta(days=1)
    yesterday_str = yesterday_date_obj.isoformat()

    # 3. 昨日のTODOリストをデータベースから取得 (現在のユーザーのもののみ)
    # user_id でフィルタリングすることを忘れないでください
    yesterday_todos = Todo.query.filter_by(date=yesterday_str, user_id=current_user.id).all()

    # 4. 取得したTODOを今日の日付で新しいTODOとして保存
    copied_count = 0
    for todo in yesterday_todos:
        # 既に今日同じタスクが存在するかチェック (任意だが重複防止に役立つ)
        # 厳密な重複チェックが必要な場合は、タスク名だけでなく詳細なども含めて比較する
        existing_today_todo = Todo.query.filter_by(
            date=selected_date,
            task=todo.task,
            user_id=current_user.id
        ).first()

        if not existing_today_todo: # 重複がなければコピー
            new_todo = Todo(
                date=selected_date,
                task=todo.task,
                status='pending', # コピー時は未完了に戻す
                description=None, # 顛末はコピーしないのが一般的
                user_id=current_user.id
            )
            db.session.add(new_todo)
            copied_count += 1
        else:
            # 既に存在する場合はスキップまたはログ出力など
            print(f"Skipping duplicate todo: {todo.task} for {selected_date}")

    db.session.commit()
    
    flash(f'昨日のTODOを{copied_count}件コピーしました！', 'success')
    return redirect(url_for('show_day', selected_date=selected_date))


# ★追加：登録 (Register) ルート
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: # すでにログインしている場合はホームへリダイレクト
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # ユーザー名の重複チェック
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('そのユーザー名はすでに使用されています。', 'danger')
            return render_template('register.html')

        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('アカウントが作成されました！ログインしてください。', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# ★追加：ログイン (Login) ルート
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # すでにログインしている場合はホームへリダイレクト
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('ログインしました！', 'success')
            next_page = request.args.get('next') # ログイン後にリダイレクトされるべきページがあれば取得
            return redirect(next_page or url_for('index'))
        else:
            flash('ログインに失敗しました。ユーザー名またはパスワードが間違っています。', 'danger')
    return render_template('login.html')

# ★追加：ログアウト (Logout) ルート
@app.route('/logout')
@login_required # ログアウトもログインしている状態でないと意味がない
def logout():
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('login')) # ログアウト後はログインページへリダイレクト

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)