import httpx
from flask import Blueprint, request, jsonify
from project.gallery.api import get_posts, Rule34Error

api_bp = Blueprint('api', __name__, url_prefix='/api')

AUTOCOMPLETE_URL = "https://api.rule34.xxx/autocomplete.php"

@api_bp.route('/autocomplete')
async def autocomplete():
    """
    Автодополнение тегов для поиска (используется Awesomplete на главной странице)
    """
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify([])

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                AUTOCOMPLETE_URL,
                params={'q': query},
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                  '(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
            # API возвращает список словарей, нам нужен только 'value'
            suggestions = [item.get('value') for item in data if isinstance(item, dict) and 'value' in item]
            
            return jsonify(suggestions[:15])  # ограничиваем количество подсказок

    except httpx.TimeoutException:
        return jsonify([])  # тихо падаем, пользователь не должен видеть ошибку
    except httpx.RequestError:
        return jsonify([])
    except Exception:
        # На всякий случай
        return jsonify([])


@api_bp.route('/mobile')
async def mobile_gallery_api():
    """
    JSON API для мобильного приложения.
    Исторически использовался путь /api/mobile (без /gallery префикса).
    """
    query_tags = request.args.get('tags', '').strip()
    page = max(0, int(request.args.get('page', 0)))
    sort_mode = request.args.get('sort', 'date')

    tags_tuple = tuple(query_tags.split()) if query_tags else ()

    try:
        posts = await get_posts(tags_tuple, page, sort_mode, (), 20)
        return jsonify(posts)
    except Rule34Error as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500