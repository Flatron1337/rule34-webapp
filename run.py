import os
from asgiref.wsgi import WsgiToAsgi
from project import create_app
from project.extensions import db

# 1. Создаем Flask приложение
flask_app = create_app()

# 2. ИСПРАВЛЕНИЕ: Принудительно создаем таблицы БД перед стартом
# Это гарантирует, что таблица 'favorite' существует до первого запроса
with flask_app.app_context():
    db.create_all()
    print("Database tables created successfully.")

# 3. Оборачиваем в ASGI для Hypercorn
app = WsgiToAsgi(flask_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port, debug=False)