import os
import httpx
import logging
import json
from project.extensions import cache

logger = logging.getLogger(__name__)

API_URL = os.environ.get("R34_API_URL", "https://api.rule34.xxx/index.php")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}


def _r34_credentials() -> tuple[str | None, str | None]:
    user_id = (os.getenv("R34_USER_ID") or "").strip()
    api_key = (os.getenv("R34_API_KEY") or "").strip().lstrip("-")
    return (user_id or None, api_key or None)


class Rule34Error(Exception):
    pass


def _media_type(file_url: str) -> str:
    """Определяет тип медиа по URL. Контракт с Flutter-клиентом (post.dart):
    ожидает 'video' / 'gif' / 'image'. Раньше gif не обрабатывался и
    отображался как статичная картинка."""
    u = (file_url or "").lower()
    if u.endswith((".mp4", ".webm")):
        return "video"
    if u.endswith(".gif"):
        return "gif"
    return "image"


def _make_cache_key(
    tags: tuple, page: int, sort_mode: str, user_blacklist: tuple, limit: int
) -> str:
    key_parts = [str(tags), str(page), sort_mode, str(user_blacklist), str(limit)]
    return f"r34:view:{'|'.join(key_parts)}"


async def get_posts(
    tags: tuple[str, ...],
    page: int,
    sort_mode: str,
    user_blacklist: tuple[str, ...],
    limit: int = 20,
) -> list[dict]:
    cache_key = _make_cache_key(tags, page, sort_mode, user_blacklist, limit)

    # Проверка кэша (не блокируем поиск при недоступном Redis)
    try:
        cached = cache.get(cache_key)
        if cached:
            return cached
    except Exception as e:
        logger.warning("Cache read failed: %s", e, exc_info=True)

    # Подготовка тегов
    negative_tags = [f"-{tag}" for tag in user_blacklist if tag]
    final_tags = list(tags)

    if sort_mode == "random":
        final_tags.append("sort:random")
    else:
        sort_tag = "sort:score:desc" if sort_mode == "score" else "sort:id:desc"
        final_tags.append(sort_tag)

    tags_for_api = final_tags + negative_tags
    tags_str = " ".join(tags_for_api)

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "tags": tags_str,
        "limit": min(limit, 1000),  # hard limit rule34
        "pid": page,
        "json": 1,
    }

    user_id, api_key = _r34_credentials()
    if not user_id or not api_key:
        raise Rule34Error(
            "Rule34 API требует ключи. Задайте R34_USER_ID и R34_API_KEY "
            "(https://rule34.xxx/index.php?page=account&s=options)"
        )
    params["user_id"] = user_id
    params["api_key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(API_URL, params=params, headers=HEADERS)
            response.raise_for_status()

            data = response.json()

            if isinstance(data, str):
                if "authentication" in data.lower():
                    raise Rule34Error(
                        "Rule34 отклонил ключи. Проверьте R34_USER_ID и R34_API_KEY на Render "
                        "(без лишних символов в начале/конце)"
                    )
                raise Rule34Error(data)

            if not isinstance(data, list):
                return []

            processed = []
            for post in data:
                # Лучшее качество превью
                preview_url = (
                    post.get("sample_url")
                    or post.get("preview_url")
                    or post.get("file_url")
                )

                processed.append(
                    {
                        "id": int(post.get("id", 0)),
                        "score": int(post.get("score", 0)),
                        "tags": post.get("tags", ""),
                        "preview_url": preview_url,
                        "sample_url": post.get("sample_url"),
                        "file_url": post.get("file_url"),
                        "type": _media_type(post.get("file_url", "")),
                        "width": post.get("width"),
                        "height": post.get("height"),
                    }
                )

            try:
                cache.set(cache_key, processed, timeout=300)
            except Exception as e:
                logger.warning("Cache write failed: %s", e, exc_info=True)
            return processed

    except httpx.TimeoutException:
        logger.error("Rule34 API timeout")
        raise Rule34Error("Таймаут соединения с Rule34")
    except httpx.RequestError as e:
        logger.error(f"Network error: {e}")
        raise Rule34Error("Не удалось подключиться к Rule34")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        raise Rule34Error(f"Ошибка сервера Rule34: {e.response.status_code}")
    except json.JSONDecodeError:
        logger.error("Invalid JSON from Rule34")
        raise Rule34Error("Некорректный ответ от сервера")
    except Exception as e:
        logger.exception("Unexpected error in get_posts")
        raise Rule34Error(f"Неизвестная ошибка: {str(e)}")
