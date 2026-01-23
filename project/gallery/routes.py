import httpx
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, Response, jsonify
from project.extensions import db
from project.models import Favorite
from .api import get_posts, Rule34Error

gallery_bp = Blueprint('gallery', __name__)
POST_URL_BASE = "https://rule34.xxx/index.php?page=post&s=view&id="
GALLERY_LIMIT = 20

def get_client_ip():
    """Получает IP пользователя (учитывая прокси Render)"""
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

@gallery_bp.route('/gallery')
async def show_gallery():
    query_tags = request.args.get('tags', '').strip()
    user_blacklist_str = request.args.get('blacklist', '').strip()
    page = int(request.args.get('page', 0))
    sort_mode = request.args.get('sort', 'date')

    if not query_tags and sort_mode != 'random':
        return redirect(url_for('main.index'))

    # История поиска
    if query_tags:
        history = session.get('history', [])
        if query_tags in history: history.remove(query_tags)
        history.insert(0, query_tags)
        session['history'] = history[:10]

    tags_tuple = tuple(query_tags.split()) if query_tags else tuple()
    user_blacklist_tuple = tuple(user_blacklist_str.split()) if user_blacklist_str else tuple()
    
    posts = []
    error_msg = None

    try:
        # AWAIT вызов
        posts = await get_posts(tags_tuple, page, sort_mode, user_blacklist_tuple, GALLERY_LIMIT)
    except Rule34Error as e:
        error_msg = str(e)
        flash(error_msg, "danger")

    # Получаем список ID избранного для этого IP, чтобы подсветить сердечки
    user_ip = get_client_ip()
    fav_ids = []
    # Работа с БД синхронная (SQLAlchemy async требует драйверов aiosqlite/asyncpg)
    # В контексте Flask 2.0+ и малого объема это допустимо внутри async route
    with gallery_bp.app.app_context():
        favs = Favorite.query.filter_by(user_ip=user_ip).with_entities(Favorite.post_id).all()
        fav_ids = [f.post_id for f in favs]

    page_range = range(max(0, page - 2), page + 3)

    return render_template(
        'gallery.html', 
        posts=posts, 
        page=page, 
        tags=query_tags, 
        sort_mode=sort_mode, 
        limit=GALLERY_LIMIT, 
        post_url_base=POST_URL_BASE,
        user_blacklist=user_blacklist_str, 
        page_range=page_range,
        fav_ids=fav_ids,
        error=error_msg
    )

# --- ИЗБРАННОЕ ---
@gallery_bp.route('/api/favorite', methods=['POST'])
def toggle_favorite():
    """AJAX endpoint для добавления/удаления избранного"""
    data = request.json
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

@gallery_bp.route('/favorites')
def show_favorites():
    user_ip = get_client_ip()
    favorites = Favorite.query.filter_by(user_ip=user_ip).order_by(Favorite.created_at.desc()).all()
    # Преобразуем формат объекта БД в формат словаря, ожидаемый шаблоном
    posts = [{
        'id': f.post_id,
        'file_url': f.file_url,
        'preview_url': f.preview_url,
        'type': f.media_type,
        'tags': f.tags,
        'score': 'Fav'
    } for f in favorites]
    
    return render_template('gallery.html', posts=posts, tags="Избранное", sort_mode="date", page=-1, fav_ids=[p['id'] for p in posts], is_favorites=True)


# --- ПРОКСИРОВАНИЕ (Privacy / Anti-block) ---
@gallery_bp.route('/proxy/image')
async def proxy_image():
    url = request.args.get('url')
    if not url: return "No URL provided", 400

    headers = {'User-Agent': 'Mozilla/5.0'}
    
    async with httpx.AsyncClient() as client:
        try:
            req = await client.get(url, headers=headers)
            return Response(
                req.content,
                content_type=req.headers.get('content-type', 'image/jpeg')
            )
        except Exception as e:
            return str(e), 500