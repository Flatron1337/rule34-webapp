# project/__init__.py
import os
from flask import Flask
from dotenv import load_dotenv
from .extensions import cache

def create_app():
    load_dotenv()
    app = Flask(__name__)

    # Конфигурация из переменных окружения
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_URL"] = os.getenv("CACHE_REDIS_URL") # Мы добавим это на Render
    app.config["CACHE_DEFAULT_TIMEOUT"] = 300 # 5 минут

    # Инициализация расширений
    cache.init_app(app)

    # Регистрация Blueprints
    from .main.routes import main_bp
    from .gallery.routes import gallery_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(gallery_bp)

    return app