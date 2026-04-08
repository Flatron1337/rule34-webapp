import os
import asyncio
from asgiref.wsgi import WsgiToAsgi
from project import create_app

# Создаём Flask приложение
flask_app = create_app()

# Оборачиваем в ASGI для Hypercorn
app = WsgiToAsgi(flask_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f">>> Starting Hypercorn on port {port}")
    # Для локального теста можно использовать uvicorn, но Render использует hypercorn
    import hypercorn.asyncio
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    config.use_reloader = False
    asyncio.run(hypercorn.asyncio.serve(app, config))