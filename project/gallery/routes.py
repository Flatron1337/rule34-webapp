import httpx
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, Response, jsonify
from project.extensions import db
from project.models import Favorite
from .api import get_posts, Rule34Error   # <-- правильный относительный импорт
from .api import get_posts, Rule34Error, HEADERS

gallery_bp = Blueprint('gallery', __name__)

POST_URL_BASE = "https://rule34.xxx/index.php?page=post&s=view&id="
GALLERY_LIMIT = 20

def get_client_ip():
    """Получаем реальный IP даже через прокси (Render)"""
    if forwarded := request.headers.getlist("X-Forwarded-For"):
        return forwarded[0].split(',')[0].strip()
    return request.remote_addr or "0.0.0.0"

# ====================== HTML ГАЛЕРЕЯ ======================
@gallery_bp.route('/gallery')
async def show_gallery():
    query_tags = request.args.get('tags', '').strip()
    user_blacklist_str = request.args.get('blacklist', '').strip()
    page = max(0, int(request.args.get('page', 0)))
    sort_mode = request.args.get('sort', 'date')

    if not query_tags and sort_mode != 'random':
        return redirect(url_for('main.index'))

    # История поиска
    if query_tags:
        history = session.get('history', [])
        if query_tags in history:
            history.remove(query_tags)
        history.insert(0, query_tags)
        session['history'] = history[:10]

    tags_tuple = tuple(query_tags.split()) if query_tags else ()
    blacklist_tuple = tuple(user_blacklist_str.split()) if user_blacklist_str else ()

    posts = []
    error_msg = None

    try:
        posts = await get_posts(tags_tuple, page, sort_mode, blacklist_tuple, GALLERY_LIMIT)
    except Rule34Error as e:
        error_msg = str(e)
        flash(error_msg, "danger")

    # Избранное текущего пользователя
    user_ip = get_client_ip()
    fav_ids = []
    try:
        favs = Favorite.query.filter_by(user_ip=user_ip).with_entities(Favorite.post_id).all()
        fav_ids = [f.post_id for f in favs]
    except Exception:
        pass

    return render_template(
        'gallery.html',
        posts=posts,
        page=page,
        tags=query_tags,
        sort_mode=sort_mode,
        limit=GALLERY_LIMIT,
        post_url_base=POST_URL_BASE,
        user_blacklist=user_blacklist_str,
        fav_ids=fav_ids,
        error=error_msg,
        is_favorites=False
    )

# ====================== JSON API ДЛЯ MOBILE ======================
@gallery_bp.route('/api/mobile/gallery')
async def mobile_gallery_api():
    query_tags = request.args.get('tags', '').strip()
    page = max(0, int(request.args.get('page', 0)))
    sort_mode = request.args.get('sort', 'date')

    tags_tuple = tuple(query_tags.split()) if query_tags else ()

    try:
        posts = await get_posts(tags_tuple, page, sort_mode, (), 20)
        return jsonify(posts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ====================== FAVORITES ======================
@gallery_bp.route('/api/favorite', methods=['POST'])
def toggle_favorite():
    try:
        data = request.get_json()
        user_ip = get_client_ip()
        post_id = int(data.get('post_id'))

        existing = Favorite.query.filter_by(user_ip=user_ip, post_id=post_id).first()

        if existing:
            db.session.delete(existing)
            action = 'removed'
        else:
            new_fav = Favorite(
                user_ip=user_ip,
                post_id=post_id,
                file_url=data.get('file_url'),
                preview_url=data.get('preview_url'),
                tags=data.get('tags'),
                media_type=data.get('media_type', 'image')
            )
            db.session.add(new_fav)
            action = 'added'

        db.session.commit()
        return jsonify({"status": "success", "action": action})

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@gallery_bp.route('/favorites')
def show_favorites():
    user_ip = get_client_ip()
    favorites = Favorite.query.filter_by(user_ip=user_ip)\
        .order_by(Favorite.created_at.desc()).all()

    posts = [
        {
            'id': f.post_id,
            'file_url': f.file_url,
            'preview_url': f.preview_url,
            'type': f.media_type,
            'tags': f.tags or ''
        }
        for f in favorites
    ]

    return render_template(
        'gallery.html',
        posts=posts,
        tags="",
        sort_mode="date",
        page=-1,
        fav_ids=[p['id'] for p in posts],
        is_favorites=True,
        user_blacklist=""
    )

# ====================== ПРОКСИ ИЗОБРАЖЕНИЙ ======================
@gallery_bp.route('/proxy/image')
async def proxy_image():
    url = request.args.get('url')
    if not url or not url.startswith('http'):
        return "Invalid URL", 400

    headers = {'User-Agent': HEADERS['User-Agent']}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            return Response(
                resp.content,
                content_type=resp.headers.get('content-type', 'image/jpeg')
            )
    except Exception:
        return "Proxy error", 502