import os
from asgiref.wsgi import WsgiToAsgi
from project import create_app
from project.extensions import db

# 1. Создаем Flask приложение
flask_app = create_app()

# 2. ВАЖНО: Создаем таблицы БД (favorites) перед запуском
# Это решает проблему "no such table: favorite"
with flask_app.app_context():
    try:
        db.create_all()
        print(">>> База данных и таблицы успешно инициализированы.")
    except Exception as e:
        print(f">>> Ошибка инициализации БД: {e}")

# 3. Оборачиваем в ASGI для Hypercorn
app = WsgiToAsgi(flask_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port, debug=False)