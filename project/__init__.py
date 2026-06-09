import os
from flask import Flask
from dotenv import load_dotenv
from .extensions import cache, db

def create_app():
    load_dotenv()
    app = Flask(__name__)

    # --- Конфигурация ---
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-me")
    
    # Cache: Redis в проде, SimpleCache локально без Redis
    redis_url = os.getenv("CACHE_REDIS_URL")
    if redis_url:
        app.config["CACHE_TYPE"] = "RedisCache"
        app.config["CACHE_REDIS_URL"] = redis_url
    else:
        app.config["CACHE_TYPE"] = "SimpleCache"
    app.config["CACHE_DEFAULT_TIMEOUT"] = int(os.getenv("CACHE_TIMEOUT", 300))

    # SQLite DB (для Render используем /tmp или instance)
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../instance")
    os.makedirs(instance_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(instance_path, 'favorites.db')}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Инициализация расширений
    cache.init_app(app)
    db.init_app(app)

    # Создаём таблицы
    with app.app_context():
        db.create_all()

    # Регистрация Blueprints
    from .main.routes import main_bp
    from .gallery.routes import gallery_bp
    from .api.routes import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(gallery_bp)
    app.register_blueprint(api_bp)
    return app