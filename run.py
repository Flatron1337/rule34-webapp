import os
from project import create_app

app = create_app()

if __name__ == "__main__":
    # Render предоставляет порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    # Debug=False важно для продакшена
    app.run(host='0.0.0.0', port=port, debug=False)