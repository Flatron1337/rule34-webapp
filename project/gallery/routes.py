# project/gallery/routes.py
from flask import Blueprint, render_template, request, session, redirect, url_for
from .api import fetch_posts # Импортируем нашу новую синхронную функцию

gallery_bp = Blueprint('gallery', __name__)
POST_URL_BASE = "https://rule34.xxx/index.php?page=post&s=view&id="
GALLERY_LIMIT = 20

# УБИРАЕМ 'async' ОТСЮДА
@gallery_bp.route('/gallery')
def show_gallery():
    """Основной маршрут для отображения результатов поиска."""
    query_tags = request.args.get('tags', '').strip()
    user_blacklist_str = request.args.get('blacklist', '').strip()
    page = int(request.args.get('page', 0))
    sort_mode = request.args.get('sort', 'date')

    if not query_tags and sort_mode != 'random':
        return redirect(url_for('main.index'))

    if query_tags:
        history = session.get('history', [])
        if query_tags in history: history.remove(query_tags)
        history.insert(0, query_tags)
        session['history'] = history[:10]

    tags_tuple = tuple(query_tags.split()) if query_tags else tuple()
    user_blacklist_tuple = tuple(user_blacklist_str.split()) if user_blacklist_str else tuple()
    
    # УБИРАЕМ 'await' ОТСЮДА
    posts = fetch_posts(tags_tuple, page, sort_mode, user_blacklist_tuple, GALLERY_LIMIT)
    
    page_range = range(max(0, page - 2), page + 3)

    return render_template(
        'gallery.html', posts=posts, page=page, tags=query_tags, 
        sort_mode=sort_mode, limit=GALLERY_LIMIT, post_url_base=POST_URL_BASE,
        user_blacklist=user_blacklist_str, page_range=page_range
    )