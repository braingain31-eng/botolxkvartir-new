from telethon.sessions import StringSession
from telethon.sessions.base import Session
from database.firebase_db import db
import pickle
import base64
import logging

logger = logging.getLogger(__name__)

class FirestoreSession(Session):
    """
    Хранит сессию Telethon в Firestore.
    Документ: sessions/telegram_parser
    """
    def __init__(self, session_name='telegram_parser'):
        super().__init__(session_name)
        self._doc_ref = db.collection('sessions').document(session_name)
        self._load()

    def _load(self):
        """Загружает сессию из Firestore"""
        doc = self._doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            serialized = data.get('data')
            if serialized:
                try:
                    decoded = base64.b64decode(serialized)
                    loaded = pickle.loads(decoded)
                    self._dc_id = loaded.get('dc_id')
                    self._server_address = loaded.get('server_address')
                    self._port = loaded.get('port')
                    self._auth_key = loaded.get('auth_key')
                    self._user_id = loaded.get('user_id')
                    self._takeout_id = loaded.get('takeout_id')
                    logger.info(f"Сессия успешно загружена из Firestore: {self._session_name}")
                except Exception as e:
                    logger.error(f"Ошибка загрузки сессии из Firestore: {e}")
        else:
            logger.info(f"Новая сессия будет создана: {self._session_name}")

    def save(self):
        """Сохраняет сессию в Firestore"""
        data = {
            'dc_id': self._dc_id,
            'server_address': self._server_address,
            'port': self._port,
            'auth_key': self._auth_key,
            'user_id': self._user_id,
            'takeout_id': self._takeout_id
        }
        serialized = base64.b64encode(pickle.dumps(data)).decode('utf-8')
        self._doc_ref.set({'data': serialized})
        logger.info(f"Сессия сохранена в Firestore: {self._session_name}")

    def delete(self):
        """Удаляет сессию"""
        self._doc_ref.delete()
        logger.info(f"Сессия удалена из Firestore: {self._session_name}")