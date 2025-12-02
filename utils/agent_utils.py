# utils/agent_utils.py
from datetime import datetime, timedelta
from database.firebase_db import get_user, create_or_update_user, update_paid_until
import logging

logger = logging.getLogger(__name__)

def _get_current_week():
    """Возвращает строку 'YYYY-WW' — год и номер недели"""
    return datetime.utcnow().strftime("%Y-%W")

def _reset_week_if_needed(user_data: dict, user_id: int):
    """Сбрасывает счётчик, если началась новая неделя"""
    current_week = _get_current_week()
    if user_data.get("week_start") != current_week:
        create_or_update_user(
            user_id,
            added_this_week=0,
            week_start=current_week
        )
        return True
    return False

def check_and_apply_agent_bonus(user_id: int) -> bool:
    """
    Проверяет, набрал ли риэлтор 5 объектов за неделю.
    Если да — даёт +7 дней премиум-доступа.
    Возвращает True, если бонус был активирован.
    """
    try:
        user = get_user(user_id)
        if not user or user.get("user_type") != "agent":
            return False

        # Сброс счётчика при новой неделе
        was_reset = _reset_week_if_needed(user, user_id)
        user = get_user(user_id)  # Перечитываем после сброса

        added_this_week = user.get("added_this_week", 0)

        if added_this_week >= 5:
            # Проверяем, не было ли уже бонуса на этой неделе
            if user.get("bonus_given_this_week") == _get_current_week():
                return False  # Уже давали на этой неделе

            # Даём +7 дней
            update_paid_until(user_id, days=7)

            # Помечаем, что бонус уже выдан на этой неделе
            create_or_update_user(
                user_id,
                bonus_given_this_week=_get_current_week()
            )

            logger.info(f"Агент {user_id} получил бонус +7 дней за 5+ объектов")
            return True

        return False

    except Exception as e:
        logger.error(f"Ошибка в check_and_apply_agent_bonus для {user_id}: {e}")
        return False

def increment_agent_property_count(user_id: int) -> tuple[int, bool]:
    """
    Увеличивает счётчик добавленных объектов за неделю.
    Возвращает: (текущее количество, был ли выдан бонус)
    """
    try:
        user = get_user(user_id)
        if not user:
            create_or_update_user(user_id, added_this_week=1, week_start=_get_current_week())
            return 1, False

        # Сброс при новой неделе
        _reset_week_if_needed(user, user_id)
        user = get_user(user_id)  # перечитываем

        current_count = (user.get("added_this_week", 0) + 1)

        create_or_update_user(
            user_id,
            added_this_week=current_count,
            last_add_date=datetime.utcnow().isoformat()
        )

        # Проверяем бонус
        bonus_given = check_and_apply_agent_bonus(user_id)

        return current_count, bonus_given

    except Exception as e:
        logger.error(f"Ошибка в increment_agent_property_count: {e}")
        return 0, False