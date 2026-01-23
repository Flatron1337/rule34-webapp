import os
from asgiref.wsgi import WsgiToAsgi
from project import create_app

# 1. Создаем стандартное Flask приложение (WSGI)
flask_app = create_app()

# 2. Оборачиваем его в адаптер ASGI.
# Hypercorn будет использовать именно переменную 'app', так как она ASGI-совместима.
app = WsgiToAsgi(flask_app)

# 3. Этот блок нужен только если вы запускаете файл локально через 'python run.py'
# На Render он игнорируется, так как там работает Hypercorn
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # Запускаем flask_app, так как метод .run() есть только у него
    flask_app.run(host='0.0.0.0', port=port, debug=False)