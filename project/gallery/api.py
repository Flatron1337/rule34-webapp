# project/gallery/api.py
import os
import httpx
import logging
from project.extensions import cache

logger = logging.getLogger(__name__)

# --- КОНСТАНТЫ ---
API_URL = "https://api.rule34.xxx/index.php"
HEADERS = {'User-Agent': 'Mozilla/5.0 ...'} # Ваш User-Agent
BLACKLISTED_TAGS = ['loli', 'shota', 'cub', 'gore', 'scat', 'toddler']
R34_USER_ID = os.getenv("R34_USER_ID")
R34_API_KEY = os.getenv("R34_API_KEY")

@cache.memoize(timeout=300) # Кэшируем результат на 5 минут
async def fetch_posts(tags: tuple, page: int, sort_mode: str, user_blacklist: tuple, limit: int) -> list:
    """Асинхронно запрашивает посты с API. Результат кэшируется."""
    logger.info(f"Запрос к API (не из кэша): {tags}, страница {page}")
    
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
        "limit": limit, "pid": page, "json": 1, "user_id": R34_USER_ID, "api_key": R34_API_KEY
    }
    
    try:
        async with httpx.AsyncClient() as client:
            api_response = await client.get(API_URL, params=params, headers=HEADERS, timeout=30)
            api_response.raise_for_status()
            posts = api_response.json()
            return posts if isinstance(posts, list) else []
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error(f"Ошибка при запросе к API: {e}", exc_info=True)
        return []