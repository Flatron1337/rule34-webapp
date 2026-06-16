import logging

import httpx
from flask import (
    Blueprint, render_template, request, session, redirect, url_for,
    flash, Response, jsonify, stream_with_context,
)
from project.extensions import db
from project.models import Favorite
from .api import get_posts, Rule34Error, HEADERS, _media_type

logger = logging.getLogger(__name__)

gallery_bp = Blueprint('gallery', __name__)

POST_URL_BASE = "https://rule34.xxx/index.php?page=post&s=view&id="
GALLERY_LIMIT = 20


def _parse_page(raw, default: int = 0) -> int:
    """Безопасный парсинг номера страницы. Возвращает default при
    отсутствии/нечисловом значении, отсекает отрицательные."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(0, value)

def get_client_ip():
    """
    Реальный IP клиента даже через прокси/балансировщик Render.

    Безопасность: НЕ используем первый X-Forwarded-For — его можно подделать,
    добавив произвольное значение слева (client-controlled), что позволило бы
    читать/удалять чужие избранное по подменному IP (IDOR).

    Приоритет:
      1. X-Real-IP — ставится доверенным балансировщиком Render, не подделывается клиентом.
      2. request.remote_addr — IP прямого TCP-соединения (надёжный фолбэк).
      3. правый край X-Forwarded-For — последний хоп (ближайший доверенный прокси).
    """
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.remote_addr:
        return request.remote_addr
    if forwarded := request.headers.getlist("X-Forwarded-For"):
        # Берём ПРАВЫЙ край — это последний доверенный прокси перед нами.
        last_hop = forwarded[0].split(",")[-1].strip()
        return last_hop
    return "0.0.0.0"

# ====================== HTML ГАЛЕРЕЯ ======================
@gallery_bp.route('/gallery')
async def show_gallery():
    query_tags = request.args.get('tags', '').strip()
    user_blacklist_str = request.args.get('blacklist', '').strip()
    page = _parse_page(request.args.get('page', 0))
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
    page = _parse_page(request.args.get('page', 0))
    sort_mode = request.args.get('sort', 'date')

    tags_tuple = tuple(query_tags.split()) if query_tags else ()

    try:
        posts = await get_posts(tags_tuple, page, sort_mode, (), 20)
        return jsonify(posts)
    except Rule34Error as e:
        # Ошибка вышестоящего Rule34 API — 502 Bad Gateway.
        return jsonify({"error": str(e)}), 502
    except Exception:
        # Не утекаем внутренние детали (пути, traceback) наружу; пишем в лог.
        logger.exception("mobile_gallery_api failed")
        return jsonify({"error": "Internal server error"}), 500

# ====================== FAVORITES ======================
@gallery_bp.route('/api/favorite', methods=['POST'])
def toggle_favorite():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Invalid JSON body"}), 400

    raw_id = data.get('post_id')
    try:
        post_id = int(raw_id)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "post_id must be an integer"}), 400

    # file_url — NOT NULL в модели Favorite; без проверки пустое значение
    # приводило бы к IntegrityError на commit → 500 вместо осмысленной 400.
    file_url = data.get('file_url')
    if not file_url or not isinstance(file_url, str):
        return jsonify({"status": "error", "message": "file_url is required"}), 400

    try:
        user_ip = get_client_ip()

        existing = Favorite.query.filter_by(user_ip=user_ip, post_id=post_id).first()

        if existing:
            db.session.delete(existing)
            action = 'removed'
        else:
            new_fav = Favorite(
                user_ip=user_ip,
                post_id=post_id,
                file_url=file_url,
                preview_url=data.get('preview_url'),
                tags=data.get('tags'),
                media_type=data.get('media_type') or _media_type(file_url),
            )
            db.session.add(new_fav)
            action = 'added'

        db.session.commit()
        return jsonify({"status": "success", "action": action})

    except Exception:
        db.session.rollback()
        logger.exception("toggle_favorite failed")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

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

# ====================== ПРОКСИ МЕДИА ======================
_HOP_BY_HEADERS = frozenset({
    'content-encoding',
    'transfer-encoding',
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailers',
    'upgrade',
})


def _validate_proxy_url(url: str | None) -> str | None:
    if not url or not url.startswith('http'):
        return None

    from urllib.parse import urlparse
    host = (urlparse(url).hostname or '').lower()
    if not host.endswith('rule34.xxx'):
        return None

    return url


def _proxy_request_headers() -> dict[str, str]:
    headers = {'User-Agent': HEADERS['User-Agent']}
    if range_header := request.headers.get('Range'):
        headers['Range'] = range_header
    return headers


def _filter_proxy_headers(headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _HOP_BY_HEADERS
    }


@gallery_bp.route('/proxy/image')
def proxy_image():
    url = _validate_proxy_url(request.args.get('url'))
    if not url:
        return "Invalid URL", 400

    headers = _proxy_request_headers()
    try:
        # Sync-стриминг: WsgiToAsgi обёртка не поддерживает async-генераторы
        # в Flask Response — Flask-WSGI видит 'function' object is not iterable.
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            req = client.build_request('GET', url, headers=headers)
            resp = client.send(req, stream=True)
            if resp.status_code >= 400:
                resp.close()
                return "Proxy error", 502
            response_headers = _filter_proxy_headers(resp.headers)
            content_type = resp.headers.get('content-type', 'image/jpeg')

            def generate():
                try:
                    for chunk in resp.iter_raw():
                        yield chunk
                finally:
                    resp.close()

            return Response(
                stream_with_context(generate()),
                content_type=content_type,
                headers=response_headers,
            )
    except Exception:
        logger.warning("proxy_image failed", exc_info=True)
        return "Proxy error", 502


@gallery_bp.route('/proxy/video', methods=['GET', 'HEAD'])
def proxy_video():
    url = _validate_proxy_url(request.args.get('url'))
    if not url:
        return "Invalid URL", 400

    headers = _proxy_request_headers()

    try:
        # Sync-стриминг: async def generate() не работает через WsgiToAsgi,
        # поэтому используем sync httpx.Client (как было изначально).
        with httpx.Client(timeout=httpx.Timeout(120.0), follow_redirects=True) as client:
            method = 'HEAD' if request.method == 'HEAD' else 'GET'
            req = client.build_request(method, url, headers=headers)
            resp = client.send(req, stream=True)

            if resp.status_code >= 400:
                resp.close()
                return "Proxy error", 502

            response_headers = _filter_proxy_headers(resp.headers)

            if request.method == 'HEAD':
                resp.close()
                return Response('', status=resp.status_code, headers=response_headers)

            def generate():
                try:
                    for chunk in resp.iter_raw():
                        yield chunk
                finally:
                    resp.close()

            return Response(
                stream_with_context(generate()),
                status=resp.status_code,
                headers=response_headers,
            )
    except Exception:
        logger.warning("proxy_video failed", exc_info=True)
        return "Proxy error", 502