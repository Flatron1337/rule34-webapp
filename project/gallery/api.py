import os
import httpx
import logging
import json
from project.extensions import cache

logger = logging.getLogger(__name__)

API_URL = "https://api.rule34.xxx/index.php"
# Эмулируем браузер
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}

BLACKLISTED_TAGS = ['loli', 'shota', 'cub', 'gore', 'scat', 'toddler']

R34_USER_ID = os.getenv("R34_USER_ID")
R34_API_KEY = os.getenv("R34_API_KEY")

class Rule34Error(Exception):
    pass

def _make_cache_key(tags, page, sort_mode, user_blacklist, limit):
    """Создает уникальный ключ для кэша"""
    key_parts = [str(tags), str(page), sort_mode, str(user_blacklist), str(limit)]
    return "view_cache:" + "|".join(key_parts)

async def get_posts(tags: tuple, page: int, sort_mode: str, user_blacklist: tuple, limit: int) -> list:
    """
    Асинхронная функция получения постов с ручным кэшированием Redis.
    """
    # 1. Проверяем кэш
    cache_key = _make_cache_key(tags, page, sort_mode, user_blacklist, limit)
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info(f"HIT Cache: {cache_key}")
        return cached_data

    # 2. Подготовка тегов
    all_blacklist = BLACKLISTED_TAGS + list(user_blacklist)
    negative_tags = [f"-{tag}" for tag in all_blacklist if tag]
    
    final_tags = list(tags)
    if sort_mode == 'random':
        final_tags.append('sort:random')
        sort_tag = "" 
    else:
        sort_tag = "sort:score:desc" if sort_mode == 'score' else "sort:id:desc"

    tags_for_api = final_tags + negative_tags
    if sort_tag: tags_for_api.append(sort_tag)

    tags_str_for_api = " ".join(tags_for_api)
    
    params = {
        "page": "dapi", "s": "post", "q": "index", "tags": tags_str_for_api,
        "limit": limit, "pid": page, "json": 1
    }
    
    if R34_USER_ID: params["user_id"] = R34_USER_ID
    if R34_API_KEY: params["api_key"] = R34_API_KEY

    # 3. Асинхронный запрос
    logger.info(f"Запрос к API: {tags_str_for_api}, page={page}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(API_URL, params=params, headers=HEADERS, timeout=15.0)
            response.raise_for_status()
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                # Иногда API возвращает пустую строку при отсутствии результатов
                if not response.text.strip():
                    return []
                logger.error(f"Invalid JSON from API: {response.text[:100]}")
                raise Rule34Error("Ошибка чтения ответа от API")

            if not isinstance(data, list):
                return []

            # 4. Нормализация данных (выбираем правильные URL для превью)
            processed_posts = []
            for post in data:
                # API R34 обычно возвращает: file_url, preview_url, sample_url
                # Иногда sample_url может отсутствовать
                processed_posts.append({
                    "id": post.get("id"),
                    "score": post.get("score"),
                    "tags": post.get("tags", ""),
                    # Оптимизация трафика:
                    "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                    "sample_url": post.get("sample_url") or post.get("file_url"),
                    "file_url": post.get("file_url"),
                    "type": "video" if post.get("file_url", "").endswith((".mp4", ".webm")) else "image",
                    "width": post.get("width"),
                    "height": post.get("height")
                })

            # 5. Сохраняем в кэш (5 минут)
            cache.set(cache_key, processed_posts, timeout=300)
            return processed_posts

    except httpx.RequestError as e:
        logger.error(f"Network error: {e}")
        raise Rule34Error("Не удалось соединиться с сервером Rule34")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        raise Rule34Error(f"Ошибка API: {e.response.status_code}")