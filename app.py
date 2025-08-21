# app.py
import os
import httpx
import logging
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for
from dotenv import load_dotenv
from cachetools import TTLCache

# --- ИНИЦИАЛИЗАЦИЯ И КОНФИГУРАЦИЯ ---
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise ValueError("Необходимо установить SECRET_KEY в .env файле!")

# --- НАСТРОЙКА ЛОГИРОВАНИЯ (из вашего бота) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    handlers=[
        logging.FileHandler('app_activity.log', mode='w'),
        logging.StreamHandler()
    ])
logger = logging.getLogger(__name__)

# --- КЭШИРОВАНИЕ ---
# Кэш на 100 запросов, где каждый результат хранится 5 минут (300 секунд)
api_cache = TTLCache(maxsize=100, ttl=300)

# --- КОНСТАНТЫ ---
API_URL = "https://api.rule34.xxx/index.php"
POST_URL_BASE = "https://rule34.xxx/index.php?page=post&s=view&id="
HEADERS = {
    'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
}
GALLERY_LIMIT = 50
BLACKLISTED_TAGS = ['loli', 'shota', 'cub', 'gore', 'scat', 'toddler']
R34_USER_ID = os.getenv("R34_USER_ID")
R34_API_KEY = os.getenv("R34_API_KEY")


# --- БЭКЕНД: ЛОГИКА ПОЛУЧЕНИЯ ДАННЫХ ---

async def fetch_posts(tags: list, page: int, sort_mode: str, user_blacklist: list) -> list:
    """Асинхронно запрашивает посты с API, использует кэш."""
    
    # Создаем уникальный ключ для кэша из всех параметров
    cache_key = (tuple(sorted(tags)), page, sort_mode, tuple(sorted(user_blacklist)))
    
    # Если результат есть в кэше, возвращаем его
    if cache_key in api_cache:
        logger.info(f"Найден кэш для запроса: {tags}, страница {page}")
        return api_cache[cache_key]

    logger.info(f"Новый запрос к API: {tags}, страница {page}")
    
    all_blacklist = BLACKLISTED_TAGS + user_blacklist
    negative_tags = [f"-{tag}" for tag in all_blacklist if tag] # Исключаем пустые теги
    
    # ИСПРАВЛЕНИЕ: Создаем копию списка тегов, чтобы избежать побочных эффектов
    final_tags = tags.copy()
    
    # Обработка тега random
    if sort_mode == 'random':
        final_tags.append('sort:random')
        # Для случайной сортировки API не использует sort:id или sort:score
        sort_tag = "" 
    else:
        sort_tag = "sort:score:desc" if sort_mode == 'score' else "sort:id:desc"

    tags_for_api = final_tags + negative_tags
    if sort_tag:
        tags_for_api.append(sort_tag)

    tags_str_for_api = " ".join(tags_for_api)
    
    params = {
        "page": "dapi", "s": "post", "q": "index", "tags": tags_str_for_api,
        "limit": GALLERY_LIMIT, "pid": page, "json": 1, "user_id": R34_USER_ID,
        "api_key": R34_API_KEY
    }
    
    try:
        async with httpx.AsyncClient() as client:
            api_response = await client.get(API_URL, params=params, headers=HEADERS, timeout=30)
            api_response.raise_for_status()
            posts = api_response.json()
            result = posts if isinstance(posts, list) else []
            # Сохраняем результат в кэш
            api_cache[cache_key] = result
            return result
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error(f"Ошибка при запросе к API: {e}", exc_info=True)
        return []

# --- ФРОНТЕНД: МАРШРУТЫ И ОТОБРАЖЕНИЕ СТРАНИЦ ---

@app.route('/')
def index():
    """Отображает главную страницу с формой поиска и историей."""
    search_history = session.get('history', [])
    return render_template('index.html', history=search_history)


@app.route('/gallery')
async def gallery():
    """Основной маршрут для отображения результатов поиска."""
    query_tags = request.args.get('tags', '').strip()
    user_blacklist_str = request.args.get('blacklist', '').strip()
    page = int(request.args.get('page', 0))
    sort_mode = request.args.get('sort', 'date')

    # ИСПРАВЛЕНИЕ: Разрешаем пустые теги, только если sort_mode='random'
    if not query_tags and sort_mode != 'random':
        return redirect(url_for('index'))

    # Логика истории поиска: добавляем, только если есть реальные теги
    if query_tags:
        if 'history' not in session:
            session['history'] = []
        
        history = session['history']
        if query_tags in history:
            history.remove(query_tags)
        history.insert(0, query_tags)
        session['history'] = history[:10] # Храним последние 10 запросов

    # Превращаем строки в списки, правильно обрабатывая пустые строки
    tags_list = query_tags.split() if query_tags else []
    user_blacklist = user_blacklist_str.split() if user_blacklist_str else []
    
    posts = await fetch_posts(tags_list, page, sort_mode, user_blacklist)
    
    # Логика для продвинутой пагинации
    page_range = range(max(0, page - 2), page + 3)

    return render_template(
        'gallery.html', 
        posts=posts, page=page, tags=query_tags, sort_mode=sort_mode,
        limit=GALLERY_LIMIT, post_url_base=POST_URL_BASE,
        user_blacklist=user_blacklist_str, page_range=page_range
    )

@app.route('/random')
def random_post():
    """Перенаправляет на поиск случайного поста."""
    tags = request.args.get('tags', '') # Можно искать случайное из определенной категории
    # Для случайного поста устанавливаем sort_mode='random', который обработает fetch_posts
    return redirect(url_for('gallery', tags=tags, sort='random'))


# --- ЗАПУСК ВЕБ-СЕРВЕРА ---
if __name__ == "__main__":
    # Команда для запуска: hypercorn app:app --reload
    logger.info("Запуск приложения...")
    app.run(host='0.0.0.0', port=8080, debug=True)