import os
import logging
from flask import Flask
from dotenv import load_dotenv
from .extensions import cache, db
from .admin.firebase_admin import init_firebase_admin

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)

    # --- Конфигурация ---
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-me")
    
    # Redis Cache
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_URL"] = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0")
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
        app.logger.info(">>> Database tables created/verified")

    # Firebase
    firebase_ready = init_firebase_admin()
    app.config["FIREBASE_ADMIN_READY"] = firebase_ready

# Регистрация Blueprints
    from .main.routes import main_bp
    from .gallery.routes import gallery_bp
    from .api.routes import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(gallery_bp)
    app.register_blueprint(api_bp)

    # Admin blueprint только если файл существует (пока его нет)
    if firebase_ready:
        try:
            from .admin.routes import admin_bp
            app.register_blueprint(admin_bp)
            app.logger.info("Admin routes registered")
        except ImportError:
            app.logger.info("Admin routes skipped (file not found)")

    app.logger.info(">>> Application created successfully")
    return app