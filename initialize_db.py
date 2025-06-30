# initialize_db.py
import os
from app import app, db

# アプリケーションコンテキスト内でデータベースを初期化
with app.app_context():
    db.create_all()
    print("Database tables created successfully (or already exist).")

    # ★重要: 初回デプロイ時のみ、ここに初期ユーザー作成コードを置く
    # すでにユーザーがいるか確認してから作成する
    from app import User, bcrypt # Userモデルとbcryptをインポート
    if not User.query.filter_by(username='admin').first(): # 例として 'admin' ユーザー
        hashed_password = bcrypt.generate_password_hash('your_initial_password').decode('utf-8') # ★パスワードを安全なものに変更！
        initial_user = User(username='admin', password=hashed_password)
        db.session.add(initial_user)
        db.session.commit()
        print("Initial user 'admin' created.")
    else:
        print("Initial user 'admin' already exists.")