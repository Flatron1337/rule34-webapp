# project/main/routes.py
from flask import Blueprint, render_template, session, redirect, url_for, request

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Отображает главную страницу с формой поиска и историей."""
    search_history = session.get('history', [])
    return render_template('index.html', history=search_history)

@main_bp.route('/random')
def random_post():
    """Перенаправляет на поиск случайного поста."""
    tags = request.args.get('tags', '')
    return redirect(url_for('gallery.show_gallery', tags=tags, sort='random'))