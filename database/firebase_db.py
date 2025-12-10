# database/firebase_db.py — ПОЛНОСТЬЮ РАБОЧАЯ ВЕРСИЯ С СОРТИРОВКОЙ (Нояб  рь 2025)

import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import firestore as fs_admin
from google.cloud.firestore_v1 import FieldFilter
from datetime import datetime, timedelta
import config
import logging

logger = logging.getLogger(__name__)

# Инициализация Firebase
def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# Глобальный клиент
db = init_firebase()


# === USERS ===
def get_user(user_id: int):
    doc = db.collection('users').document(str(user_id)).get()
    return doc.to_dict() if doc.exists else None


def create_or_update_user(user_id: int, **data):
    doc_ref = db.collection('users').document(str(user_id))
    data.setdefault('last_seen', datetime.utcnow().isoformat())
    doc_ref.set(data, merge=True)


def update_paid_until(user_id: int, days: int):
    paid_until = (datetime.utcnow() + timedelta(days=days)).isoformat()
    create_or_update_user(user_id, paid_until=paid_until)


# === PROPERTIES — ГЛАВНАЯ ФУНКЦИЯ С ПОДДЕРЖКОЙ order_by ===
def get_properties(
    filters: dict = None,
    order_by: str = None,      # Новый параметр: "price_day", "-price_day", "created_at", "-created_at"
    limit: int = 10
):
    """
    Универсальная выборка активных объектов
    filters: {"price_day__lte": 300, "area": "Anjuna"}
    order_by: "price_day" (по возрастанию), "-price_day" (по убыванию)
    """
    try:
        # Базовый запрос — только активные объекты
        query = db.collection('properties').where(filter=FieldFilter("status", "==", "active"))

        # Применяем фильтры
        if filters:
            for k, v in filters.items():
                if v is None:
                    continue
                if '__lte' in k:
                    field = k.replace('__lte', '')
                    query = query.where(filter=FieldFilter(field, '<=', v))
                elif '__gte' in k:
                    field = k.replace('__gte', '')
                    query = query.where(filter=FieldFilter(field, '>=', v))
                elif '__in' in k:
                    field = k.replace('__in', '')
                    query = query.where(filter=FieldFilter(field, 'in', v))
                else:
                    query = query.where(filter=FieldFilter(k, '==', v))

        # Применяем сортировку
        if order_by:
            field_name = order_by.lstrip('-')
            direction = fs_admin.Query.DESCENDING if order_by.startswith('-') else fs_admin.Query.ASCENDING
            query = query.order_by(field_name, direction=direction)

        # Лимит
        query = query.limit(limit)

        # Выполняем
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)

        return results

    except Exception as e:
        logger.error(f"Ошибка в get_properties: {e}")
        return []


# === Создание обычного объекта (для парсера и т.д.) ===
def create_property(data: dict):
    doc_ref = db.collection('properties').document()
    data['id'] = doc_ref.id
    data['created_at'] = datetime.utcnow().isoformat()
    data['status'] = data.get('status', 'active')
    doc_ref.set(data)
    return data['id']


# === AGENT PROPERTIES ===
def create_agent_property(agent_id: int, data: dict):
    user = get_user(agent_id) or {}
    week = datetime.utcnow().strftime("%Y-%W")
    
    if user.get('week_start') != week:
        create_or_update_user(agent_id, added_this_week=0, week_start=week)
    
    doc_ref = db.collection('agent_properties').document()
    data.update({
        'agent UU_id': agent_id,
        'created_at': datetime.utcnow().isoformat(),
        'week_start': week,
        'status': 'active'
    })
    doc_ref.set(data)
    
    added = (user.get('added_this_week', 0) + 1)
    create_or_update_user(agent_id, added_this_week=added)
    
    bonus_given = False
    if added >= 5:
        update_paid_until(agent_id, 7)
        bonus_given = True

    return doc_ref.id, bonus_given


# === Получение объекта по ID (для детализации) ===
def get_property_by_id(prop_id: str) -> dict | None:
    try:
        doc_ref = db.collection("properties").document(prop_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        # Попробуем в agent_properties
        doc_ref = db.collection("agent_properties").document(prop_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
    except Exception as e:
        logger.error(f"Ошибка get_property_by_id {prop_id}: {e}")
    return None

def delete_all_properties() -> int:
    """
    Удаляет все документы из коллекции properties.
    Возвращает количество удаленных документов.
    """
    try:
        collection_ref = db.collection('properties')
        docs = collection_ref.stream()
        deleted_count = 0
        
        batch = db.batch()
        batch_size = 500  # Максимальный размер батча
        
        for doc in docs:
            batch.delete(doc.reference)
            deleted_count += 1
            
            # Выполняем батч каждые 500 документов
            if deleted_count % batch_size == 0:
                batch.commit()
                batch = db.batch()
        
        # Выполняем последний батч, если остались документы
        if deleted_count % batch_size != 0:
            batch.commit()
        
        logger.info(f"Удалено {deleted_count} документов из коллекции properties")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Ошибка при удалении документов из коллекции properties: {e}")
        return 0

def get_user_premium_info(user_id: int):
    user = get_user(user_id)
    if not user:
        create_or_update_user(user_id, is_premium=False, premium_until=None)
        return {"is_premium": False, "days_left": 0, "expires_at": None}

    if 'is_premium' not in user or 'premium_until' not in user:
        create_or_update_user(user_id, is_premium=False, premium_until=None)
        return {"is_premium": False, "days_left": 0, "expires_at": None}

    is_premium = user['is_premium']
    premium_until_str = user['premium_until']

    if not is_premium or not premium_until_str:
        return {"is_premium": False, "days_left": 0, "expires_at": None}

    try:
        premium_until = datetime.fromisoformat(premium_until_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if now >= premium_until:
            create_or_update_user(user_id, is_premium=False)
            return {"is_premium": False, "days_left": 0, "expires_at": None}
        
        days_left = (premium_until - now).days
        return {
            "is_premium": True,
            "days_left": days_left,
            "expires_at": premium_until.isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка премиум для {user_id}: {e}")
        return {"is_premium": False, "days_left": 0, "expires_at": None}