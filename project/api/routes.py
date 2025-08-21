# project/api/routes.py
import httpx
from flask import Blueprint, request, jsonify

api_bp = Blueprint('api', __name__)
AUTOCOMPLETE_URL = "https://api.rule34.xxx/autocomplete.php"

@api_bp.route('/api/autocomplete')
async def autocomplete():
    """
    Принимает частичный тег от фронтенда, запрашивает подсказки у API Rule34
    и возвращает их в формате JSON.
    """
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    try:
        async with httpx.AsyncClient() as client:
            # API rule34 ожидает параметр 'q' для автодополнения
            response = await client.get(AUTOCOMPLETE_URL, params={'q': query})
            response.raise_for_status()
            # API возвращает список объектов, нам нужно только поле 'value'
            suggestions = [item['value'] for item in response.json()]
            return jsonify(suggestions)
    except Exception:
        # В случае ошибки просто возвращаем пустой список
        return jsonify([])