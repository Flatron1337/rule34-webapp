import os
from flask import Flask
from dotenv import load_dotenv
from .extensions import cache, db
from .admin.firebase_admin import init_firebase_admin

def create_app():
    load_dotenv()
    app = Flask(__name__)

    # --- Конфигурация ---
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-me")
    
    # Redis Config
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_URL"] = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0")
    app.config["CACHE_DEFAULT_TIMEOUT"] = int(os.getenv("CACHE_TIMEOUT", 300))

    # DB Config (SQLite)
    # Используем /tmp/db.sqlite для Render (временное хранилище) или файл в папке
    # На бесплатном Render диск стирается при перезапуске, для персистентности нужен Render Disk
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../instance")
    os.makedirs(db_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(db_path, 'favorites.db')}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Инициализация
    cache.init_app(app)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Firebase Admin SDK (for admin APIs / reading telemetry)
    # If initialization fails, either:
    # - skip registering admin routes (default), or
    # - fail fast at startup when REQUIRE_FIREBASE_ADMIN=1.
    firebase_ready = True
    try:
        init_firebase_admin()
    except Exception as e:
        firebase_ready = False
        app.logger.exception("Firebase Admin SDK initialization failed; admin routes will be disabled.")
        if os.getenv("REQUIRE_FIREBASE_ADMIN", "").strip() in {"1", "true", "True", "yes", "YES"}:
            raise RuntimeError(
                "Firebase Admin SDK failed to initialize and REQUIRE_FIREBASE_ADMIN is set. "
                "Fix Firebase credentials/configuration or unset REQUIRE_FIREBASE_ADMIN to boot without admin routes."
            ) from e
    app.config["FIREBASE_ADMIN_READY"] = firebase_ready

    # Регистрация Blueprints
    from .main.routes import main_bp
    from .gallery.routes import gallery_bp
    from .api.routes import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(gallery_bp)
    app.register_blueprint(api_bp)
    if firebase_ready:
        from .admin.routes import admin_bp
        app.register_blueprint(admin_bp)

    return app