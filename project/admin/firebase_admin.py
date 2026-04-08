import os
import logging

logger = logging.getLogger(__name__)

def init_firebase_admin():
    """
    Заглушка для Firebase Admin SDK.
    Если понадобится настоящий Firebase — добавь сюда credentials.
    """
    try:
        firebase_creds = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if not firebase_creds:
            logger.info("Firebase credentials not provided. Running without Firebase Admin.")
            return False
        
        # Здесь будет реальная инициализация, когда добавишь JSON
        logger.info("Firebase Admin SDK initialized (stub mode)")
        return True
    except Exception as e:
        logger.warning(f"Firebase init failed: {e}. Continuing without admin features.")
        return False