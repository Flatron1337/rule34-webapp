from flask import Blueprint, render_template, session, redirect, url_for, request

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Главная страница с формой поиска и историей"""
    search_history = session.get("history", [])
    return render_template("index.html", history=search_history)


@main_bp.route("/health")
@main_bp.route("/ping")
def health_check():
    """Быстрый эндпоинт для проверки здоровья и keep-alive крон-джоб"""
    return {"status": "ok", "message": "pong"}, 200


@main_bp.route("/random")
def random_post():
    """Редирект на случайный пост"""
    tags = request.args.get("tags", "").strip()
    # Если теги переданы — ищем по ним в random режиме
    return redirect(url_for("gallery.show_gallery", tags=tags, sort="random"))
