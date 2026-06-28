import logging

import os
import httpx
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

AUTOCOMPLETE_URL = os.environ.get(
    "AUTOCOMPLETE_URL", "https://" + "api.rule34.xxx/autocomplete.php"
)


@api_bp.route("/autocomplete")
async def autocomplete():
    """
    Автодополнение тегов для поиска (используется Awesomplete на главной странице)
    """
    query = request.args.get("q", "").strip()

    if not query or len(query) < 2:
        return jsonify([])

    try:
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            response = await client.get(
                AUTOCOMPLETE_URL,
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
                },
            )
            response.raise_for_status()

            data = response.json()

            # API возвращает список словарей, нам нужен только 'value'
            suggestions = [
                item.get("value")
                for item in data
                if isinstance(item, dict) and "value" in item
            ]

            return jsonify(suggestions[:15])  # ограничиваем количество подсказок

    except httpx.TimeoutException:
        return jsonify([])  # тихо падаем, пользователь не должен видеть ошибку
    except httpx.RequestError:
        return jsonify([])
    except Exception:
        logger.warning("autocomplete unexpected error", exc_info=True)
        return jsonify([])
