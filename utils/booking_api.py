import requests
import hashlib
import time
from typing import Dict, List
import config  # Добавь в config.py: BOOKING_API_KEY, BOOKING_SECRET

def sign_request(params: Dict) -> str:
    """Генерация подписи для Booking API (SHA-256)"""
    sorted_params = sorted(params.items())
    data_to_sign = '&'.join([f"{k}={v}" for k, v in sorted_params]) + config.BOOKING_SECRET
    return hashlib.sha256(data_to_sign.encode()).hexdigest()

async def search_goa_accommodations(
    checkin: str,  # YYYY-MM-DD
    checkout: str,
    guests: int = 2,
    city: str = "Goa",
    budget_max: float = 500.0
) -> List[Dict]:
    """Поиск по Гоа через Affiliate API v3"""
    params = {
        'aid': config.BOOKING_PARTNER_ID,  # Твой Partner ID
        'city': city,
        'checkin': checkin,
        'checkout': checkout,
        'guests': guests,
        'price_max': int(budget_max * 100),  # В центах
        'order_by': 'price',  # Сортировка по цене
        'ss': 'Goa',  # Search string
        'lang': 'en',  # Или 'ru'
        'curr': 'USD'
    }
    
    # Подпись
    params['hash'] = sign_request(params)
    
    url = "https://distribution-xml.booking.com/3.0/hotels"  # Или /accommodation/search для v3
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        # Парсим результаты (адаптируй под реальный response)
        hotels = []
        for hotel in data.get('hotels', []):
            hotels.append({
                'id': hotel['hotel_id'],
                'title': hotel['hotel_name'],
                'area': hotel['city'],
                'price_day': hotel['price'] / 100,  # USD
                'guests': guests,
                'photos': [photo['url'] for photo in hotel.get('photos', [])[:4]],
                'description': hotel.get('description', ''),
                'amenities': hotel.get('facilities', []),
                'owner_type': 'agent',  # Booking — как риэлтор
                'booking_url': f"https://www.booking.com/hotel/in/{hotel['hotel_id']}.html",  # Редирект
                'contacts': None  # Скрыто до оплаты
            })
        return hotels[:10]  # Лимит
    except Exception as e:
        print(f"Booking API error: {e}")
        return []