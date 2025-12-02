# utils/payment.py
from datetime import datetime, timedelta
from aiogram.types import LabeledPrice
from config import WEEK_PRICE_USD, MONTH_PRICE_USD, WEEK_PRICE_STARS, MONTH_PRICE_STARS, CRYPTO_WALLETS

def is_saturday():
    """Проверка — суббота ли сегодня (UTC)"""
    return datetime.utcnow().weekday() == 5  # 0=Mon, 5=Sat

def get_prices_in_stars():
    """Цены в Stars с наценкой +5%"""
    base_7 = 10.0 * 1.05  # 10.5 USD
    base_30 = 20.0 * 1.05  # 21.0 USD
    stars_7 = int(base_7 * 100)   # 1050
    stars_30 = int(base_30 * 100) # 2100
    return stars_7, stars_30

def get_invoice_payload(user_id: int, days: int):
    return f"{user_id}_{days}_stars" if is_saturday() else f"{user_id}_{days}"

def create_prices(days: int):
    """Возвращает LabeledPrice в USD или Stars"""
    if is_saturday():
        stars_7, stars_30 = get_prices_in_stars()
        amount = stars_7 if days == 7 else stars_30
        return [LabeledPrice(label=f"Доступ на {days} дней (Stars)", amount=amount)]
    else:
        amount = 1000 if days == 7 else 2000  # cents
        return [LabeledPrice(label=f"Доступ на {days} дней", amount=amount)]

def get_prices(currency: str, days: int):
    if currency == "USD":
        amount = WEEK_PRICE_USD if days == 7 else MONTH_PRICE_USD
        return [LabeledPrice(label=f"Доступ на {days} дней", amount=int(amount * 100))]
    elif currency == "XTR":
        amount = WEEK_PRICE_STARS if days == 7 else STARS_MONTH_PRICE_STARS
        return [LabeledPrice(label=f"Доступ на {days} дней (Stars)", amount=amount)]
    return []

def get_payload(user_id: int, days: int, method: str):
    return f"{user_id}_{days}_{method}"

def get_price_label(days: int):
    return f"{days} дней"