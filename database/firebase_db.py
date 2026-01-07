# database/firebase_db.py — ПОЛНОСТЬЮ РАБОЧАЯ ВЕРСИЯ С СОРТИРОВКОЙ (Нояб  рь 2025)

import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import firestore as fs_admin
from google.cloud.firestore_v1 import FieldFilter, Query
from google.api_core.exceptions import FailedPrecondition
from datetime import datetime, timedelta, timezone
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

def activate_premium(user_id: int, days: int = 30, reason: str = "manual"):
    """
    Активирует премиум-подписку для пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        days: Количество дней подписки (7, 30 и т.д.)
        reason: Причина активации (для логов): "stars", "crypto", "card", "bonus", "manual"
    """
    try:
        # Точная дата окончания — UTC
        now = datetime.now(timezone.utc)
        paid_until = now + timedelta(days=days)

        # Обновляем пользователя в Firestore
        update_data = {
            "is_premium": True,
            "premium_until": paid_until.isoformat(),
            "premium_activated_at": now.isoformat(),
            "premium_source": reason,
            "premium_days_added": days,
        }

        create_or_update_user(user_id, **update_data)

        days_word = "день" if days == 1 else "дня" if 2 <= days <= 4 else "дней"
        logger.info(f"Премиум активирован: user_id={user_id}, +{days} {days_word}, до {paid_until.date()} (по {reason})")

        return True

    except Exception as e:
        logger.error(f"Ошибка активации премиума для {user_id}: {e}")
        return False

# === PROPERTIES — ГЛАВНАЯ ФУНКЦИЯ С ПОДДЕРЖКОЙ order_by ===
# def get_properties(
#     filters: dict = None,
#     order_by: str = None,      # Новый параметр: "price_day", "-price_day", "created_at", "-created_at"
#     limit: int = 10
# ):
#     """
#     Универсальная выборка активных объектов
#     filters: {"price_day__lte": 300, "area": "Anjuna"}
#     order_by: "price_day" (по возрастанию), "-price_day" (по убыванию)
#     """
#     try:
#         # Базовый запрос — только активные объекты
#         query = db.collection('properties').where(filter=FieldFilter("status", "==", "active"))

#         # Применяем фильтры
#         if filters:
#             for k, v in filters.items():
#                 if v is None:
#                     continue
#                 if '__lte' in k:
#                     field = k.replace('__lte', '')
#                     query = query.where(filter=FieldFilter(field, '<=', v))
#                 elif '__gte' in k:
#                     field = k.replace('__gte', '')
#                     query = query.where(filter=FieldFilter(field, '>=', v))
#                 elif '__in' in k:
#                     field = k.replace('__in', '')
#                     query = query.where(filter=FieldFilter(field, 'in', v))
#                 else:
#                     query = query.where(filter=FieldFilter(k, '==', v))

#         # Применяем сортировку
#         if order_by:
#             field_name = order_by.lstrip('-')
#             direction = fs_admin.Query.DESCENDING if order_by.startswith('-') else fs_admin.Query.ASCENDING
#             query = query.order_by(field_name, direction=direction)

#         # Лимит
#         query = query.limit(limit)

#         # Выполняем
#         docs = query.stream()
#         results = []
#         for doc in docs:
#             data = doc.to_dict()
#             data["id"] = doc.id
#             results.append(data)

#         return results

#     except Exception as e:
#         logger.error(f"Ошибка в get_properties: {e}")
#         return []

def get_properties(
    filters: dict | None = None,
    order_by: str | None = None,
    limit: int = 20,                    # Повысил дефолт — 10 слишком мало
    allow_inactive: bool = False        # Новый параметр — для админки
):
    """
    Универсальная выборка объектов из Firestore с поддержкой:
    - фильтров (==, >=, <=, in)
    - сортировки (asc/desc)
    - лимита
    - автоматический fallback при отсутствии индекса
    """
    try:
        collection = db.collection('properties')

        # Базовый фильтр — только активные (если не для админа)
        if not allow_inactive:
            query = collection.where(filter=FieldFilter("status", "==", "active"))
        else:
            query = collection

        # Применяем пользовательские фильтры
        if filters:
            for key, value in filters.items():
                if value is None:
                    continue

                if '__lte' in key:
                    field = key.replace('__lte', '')
                    query = query.where(filter=FieldFilter(field, '<=', value))
                elif '__gte' in key:
                    field = key.replace('__gte', '')
                    query = query.where(filter=FieldFilter(field, '>=', value))
                elif '__in' in key:
                    field = key.replace('__in', '')
                    query = query.where(filter=FieldFilter(field, 'in', value))
                else:
                    # Для == или других
                    query = query.where(filter=FieldFilter(key, '==', value))

        # Сортировка
        if order_by:
            field_name = order_by.lstrip('-')
            direction = Query.DESCENDING if order_by.startswith('-') else Query.ASCENDING
            query = query.order_by(field_name, direction=direction)

        # Лимит
        query = query.limit(limit)

        # Выполняем запрос
        docs = query.stream()

        # Современный способ: list comprehension + merge dict
        results = [doc.to_dict() | {"id": doc.id} for doc in docs]

        return results

    except FailedPrecondition as e:
        # Ошибка индекса — возвращаем fallback (по цене asc)
        logger.warning(f"Нет индекса для запроса: {e}. Используем fallback.")
        fallback_query = (
            db.collection('properties')
            .where(filter=FieldFilter("status", "==", "active"))
            .order_by("price_day_inr", direction=Query.ASCENDING)
            .limit(limit)
        )
        docs = fallback_query.stream()
        return [doc.to_dict() | {"id": doc.id} for doc in docs]

    except Exception as e:
        logger.error(f"Ошибка в get_properties: {e}", exc_info=True)
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

def get_user_premium_info(user_id: int) -> dict:
    """
    Возвращает информацию о премиуме пользователя.
    Автоматически создаёт поля, если их нет.
    """
    try:
        user = get_user(user_id)
        
        # Если пользователя нет — создаём с дефолтами
        if not user:
            create_or_update_user(user_id, is_premium=False, premium_until=None)
            return {"is_premium": False, "days_left": 0, "expires_at": None}

        # Если нет нужных полей — создаём
        if 'is_premium' not in user or 'premium_until' not in user:
            create_or_update_user(
                user_id, 
                is_premium=False, 
                premium_until=None,
                premium_source="expired"
            )
            return {"is_premium": False, "days_left": 0, "expires_at": None}

        # Проверяем статус
        if not user['is_premium'] or not user['premium_until']:
            return {"is_premium": False, "days_left": 0, "expires_at": None}

        # Парсим дату
        premium_until_str = user['premium_until']
        try:
            premium_until = datetime.fromisoformat(premium_until_str.replace('Z', '+00:00'))
        except:
            # Если дата битая — сбрасываем
            create_or_update_user(user_id, is_premium=False, premium_until=None)
            return {"is_premium": False, "days_left": 0, "expires_at": None}

        now = datetime.now(timezone.utc)

        if now >= premium_until:
            # Премиум истёк — сбрасываем
            create_or_update_user(user_id, is_premium=False, premium_until=None)
            return {"is_premium": False, "days_left": 0, "expires_at": None}

        # Правильно считаем дни (даже если осталось 5 часов — будет 1 день)
        days_left = (premium_until - now).days + 1

        return {
            "is_premium": True,
            "days_left": days_left,
            "expires_at": premium_until.isoformat()
        }

    except Exception as e:
        logger.error(f"Критическая ошибка в get_user_premium_info({user_id}): {e}")
        return {"is_premium": False, "days_left": 0, "expires_at": None}

def add_favorite(user_id: int, prop_id: str):
    doc_ref = db.collection('users').document(str(user_id))
    doc_ref.update({
        "favorites": firestore.ArrayUnion([prop_id])
    })
    logger.info(f"Добавлено в избранное: user {user_id}, prop {prop_id}")

def remove_favorite(user_id: int, prop_id: str):
    doc_ref = db.collection('users').document(str(user_id))
    doc_ref.update({
        "favorites": firestore.ArrayRemove([prop_id])
    })
    logger.info(f"Убрано из избранного: user {user_id}, prop {prop_id}")

def is_favorite(user_id: int, prop_id: str) -> bool:
    user = get_user(user_id)
    if not user or not user.get("favorites"):
        return False
    return prop_id in user["favorites"]

def delete_property(prop_id: str):
    """
    Удаляет объявление из Firestore по ID.
    Возвращает True если успешно, False если ошибка.
    """
    try:
        doc_ref = db.collection('properties').document(prop_id)
        doc_ref.delete()
        logger.info(f"Объявление успешно удалено из базы: ID {prop_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении объявления ID {prop_id}: {e}")
        return False

def create_request(user_id: int, query_text: str) -> str:
    """
    Создаёт новый запрос в collection 'requests'.
    Статус по умолчанию 'active'.
    """
    request_ref = db.collection('requests').document()
    request_id = request_ref.id
    request_ref.set({
        "user_id": user_id,
        "query_text": query_text,
        "status": "active",  # активно или неактивно
        "timestamp": datetime.utcnow().isoformat()
    })
    logger.info(f"Создан запрос ID {request_id} от user {user_id}")
    return request_id

def add_proposal(request_id: str, realtor_id: int, proposal_text: str) -> bool:
    """
    Добавляет предложение в collection 'proposals'.
    Привязка к request_id.
    """
    proposal_ref = db.collection('proposals').document()
    proposal_ref.set({
        "request_id": request_id,
        "realtor_id": realtor_id,
        "proposal_text": proposal_text,
        "timestamp": datetime.utcnow().isoformat()
    })
    logger.info(f"Добавлено предложение к запросу {request_id} от риэлтора {realtor_id}")
    return True

def get_request_status(request_id: str) -> str:
    """
    Получает статус запроса ('active' или 'inactive').
    Возвращает None, если запрос не найден.
    """
    request = db.collection('requests').document(request_id).get()
    if request.exists:
        return request.to_dict().get("status")
    logger.warning(f"Запрос ID {request_id} не найден")
    return None

def set_request_status(request_id: str, status: str):
    """
    Устанавливает статус запроса ('active' или 'inactive').
    """
    if status not in ["active", "inactive"]:
        logger.error(f"Неверный статус: {status}")
        return False

    db.collection('requests').document(request_id).update({"status": status})
    logger.info(f"Статус запроса {request_id} изменён на {status}")
    return True

def get_proposals_by_request(request_id: str, limit: int = 10, offset: int = 0) -> list:
    proposals = db.collection('proposals')\
        .where("request_id", "==", request_id)\
        .order_by("timestamp")\
        .offset(offset)\
        .limit(limit)\
        .stream()
    return [p.to_dict() for p in proposals]

def get_request(request_id: str) -> dict:
    return db.collection('requests').document(request_id).get().to_dict()

def get_user_active_requests(user_id: int) -> list:
    """
    Получает все активные запросы клиента.
    Возвращает список dict с 'request_id' и данными.
    """
    requests_ref = db.collection('requests')\
        .where("user_id", "==", user_id)\
        .where("status", "==", "active")
    docs = requests_ref.stream()

    active_requests = []
    for doc in docs:
        data = doc.to_dict()
        data["request_id"] = doc.id  # ← КЛЮЧЕВОЕ: добавляем ID документа
        active_requests.append(data)
    
    return active_requests


def deactivate_old_requests(user_id: int):
    """
    Деактивирует все старые активные запросы клиента.
    """
    active_requests = get_user_active_requests(user_id)
    for req in active_requests:
        request_id = req["request_id"]  # теперь безопасно
        db.collection('requests').document(request_id).update({"status": "inactive"})
        logger.info(f"Деактивирован старый запрос ID {request_id} для user {user_id}")