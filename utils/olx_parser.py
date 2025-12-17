# utils/olx_parser.py — ДОРАБОТАННЫЙ ПАРСЕР С ФИЛЬТРАЦИЕЙ ПО РАЙОНАМ И ЦЕНАМИ В РУПИЯХ

import logging
import urllib.request
import ssl
import re
from datetime import datetime
from database.firebase_db import create_property, get_properties
import asyncio
from lxml import etree
import time

logger = logging.getLogger(__name__)

# Новый прокси из примера
PROXY_URL = 'http://brd-customer-hl_8b4b2a1a-zone-residential_proxy2:3u94ok69p04q@brd.superproxy.io:33335'

BASE_URL = "https://www.olx.in/goa_g2001153/for-rent-houses-apartments_c1723"

# Список северных районов Гоа для фильтрации
NORTH_GOA_AREAS = [
    "Arambol", "Arambol Beach", "Aswem", "Ashwem", "Mandrem", "Morjim",
    "Kerim", "Keri", "Korgaon", "Siolim", "Chapora", "Vagator", "Anjuna",
    "Assagao", "Arpora", "Baga", "Calangute", "Candolim", "Agarwado", "Pilerne", "Palolem", "Agonda"
]

# def normalize_location(location_text: str) -> str:
#     """Улучшенная нормализация с более мягкой фильтрацией"""
#     if not location_text:
#         return "Other North Goa"
    
#     original_location = location_text
#     normalized = location_text.lower().strip()
    
#     # Убираем лишние слова
#     for word in ["goa", "north goa", "goa north", "beach", "road", "near", "opp", "opposite", "nearby"]:
#         normalized = normalized.replace(word, "").strip()
    
#     # Проверяем наличие целевых районов (более мягкая проверка)
#     for area in NORTH_GOA_AREAS:
#         area_variants = [area.lower(), area.lower().replace(" ", ""), area.lower().replace(" ", "") + "beach"]
#         for variant in area_variants:
#             if variant in normalized or variant in original_location.lower():
#                 logger.debug(f"Обнаружен район '{area}' в локации: {original_location}")
#                 return area
    
#     # Если не найдено точное соответствие, но есть упоминание Гоа, сохраняем как Other North Goa
#     if any(word in original_location.lower() for word in ["goa", "north goa"]):
#         logger.debug(f"Локация '{original_location}' не содержит конкретных районов, сохранена как Other North Goa")
#         return "Other North Goa"
    
#     logger.debug(f"Локация '{original_location}' не соответствует ни одному целевому району, пропускается")
#     return None  # Явно возвращаем None для пропуска

def normalize_location(location_text: str) -> str | None:
    """
    Проверяет, есть ли в тексте локации хотя бы один район из NORTH_GOA_AREAS.
    Всё приводится к нижнему регистру — никаких лишних слов, пляжей, дорог и т.д. не убираем.
    Возвращает название района из списка NORTH_GOA_AREAS или None.
    """
    if not location_text or not location_text.strip():
        return None

    text_lower = location_text.lower()

    for area in NORTH_GOA_AREAS:               # ← твой список: ["Anjuna", "Arpora", "Vagator", ...]
        area_lower = area.lower()
        if area_lower in text_lower:           # простая подстрока — работает даже с "anjuna beach", "vagator road" и т.д.
            logger.debug(f"Найден район '{area}' в локации: {location_text}")
            return area

    logger.debug(f"Район не найден в локации: {location_text}")
    return None

def get_page_html(page: int = 1) -> str | None:
    """Получает HTML страницы с увеличенными таймаутами и повторными попытками"""
    max_retries = 3
    base_delay = 10
    
    for attempt in range(max_retries):
        try:
            proxy_handler = urllib.request.ProxyHandler({
                'http': PROXY_URL,
                'https': PROXY_URL
            })
            
            ssl_context = ssl._create_unverified_context()
            
            opener = urllib.request.build_opener(
                proxy_handler,
                urllib.request.HTTPSHandler(context=ssl_context)
            )
            
            url = f"{BASE_URL}?page={page}&filter=private_business_eq_private"
            
            with opener.open(url, timeout=120) as response:  # Увеличенный таймаут
                if response.getcode() == 200:
                    html_content = response.read().decode('utf-8')
                    logger.info(f"Страница {page} успешно загружена: {len(html_content)} символов")
                    return html_content
                else:
                    logger.warning(f"Страница {page}: HTTP статус {response.getcode()}")
                    
        except urllib.request.HTTPError as e:
            if e.code == 502:  # Proxy Connect Timeout
                logger.warning(f"Страница {page}, попытка {attempt + 1}: Proxy Connect Timeout. Ждем {base_delay * (2 ** attempt)} секунд")
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))  # Экспоненциальная задержка
                    continue
            logger.error(f"HTTP ошибка при запросе страницы {page}: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при запросе страницы {page}, попытка {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(base_delay)
                continue
    
    logger.error(f"Не удалось загрузить страницу {page} после {max_retries} попыток")
    return None

def parse_page(html: str) -> list[dict]:
    if not html or len(html) < 10000:
        return []

    dom = etree.HTML(html)
    items = dom.xpath('.//li[contains(@data-aut-id, "itemBox")]')

    ads = []
    for item in items:
        try:
            link_path = item.xpath('.//a/@href')
            if not link_path:
                continue
            link = "https://www.olx.in" + link_path[0]
            olx_id = link.split('-i')[-1].split('?')[0].split('#')[0]

            # Пропускаем дубли
            if get_properties({"olx_id": olx_id}, limit=1):
                continue

            title = "".join(item.xpath('.//span[@data-aut-id="itemTitle"]/text()')).strip()
            price_text = "".join(item.xpath('.//span[@data-aut-id="itemPrice"]/text()')).strip()
            
            # Извлекаем цену в рупиях
            price_match = re.search(r'₹\s*([\d,]+)', price_text)
            price_inr = 0
            if price_match:
                price_inr = int(price_match.group(1).replace(',', ''))

            # Определяем район
            location_raw = "".join(item.xpath('.//span[@data-aut-id="item-location"]/text()')).strip()
            logger.debug(f"Обнаружена локация: '{location_raw}'")
            area = normalize_location(location_raw)
            logger.debug(f"Определенный район: {area}")

            # Если район не определен, пропускаем объявление
            if area is None:
                logger.debug(f"Локация '{location_raw}' не соответствует ни одному целевому району, пропускается")
                continue
            
            photo = item.xpath('.//img/@src')
            photo_url = photo[0] if photo else None

            # === НОВАЯ ЛОГИКА: парсим детали (BHK, Bathroom, sqft) ===
            details_text = "".join(item.xpath('.//span[@data-aut-id="itemDetails"]/text()')).strip()
            logger.debug(f"Детали объявления: '{details_text}'")

            bedrooms = None
            bathrooms = None
            sqft = None

            if details_text:
                # Примеры: "3 BHK - 3 Bathroom - 3000 sqft", "2 BHK - 2 baths - 1500 sq.ft"
                # Ищем число перед BHK
                bhk_match = re.search(r'(\d+)\s*BHK', details_text, re.IGNORECASE)
                if bhk_match:
                    bedrooms = int(bhk_match.group(1))

                # Ищем число перед Bathroom / bath / baths
                bath_match = re.search(r'(\d+)\s*(?:Bathroom|bath|baths)', details_text, re.IGNORECASE)
                if bath_match:
                    bathrooms = int(bath_match.group(1))

                # Ищем площадь: 3000 sqft / sq.ft / sq ft / square feet
                sqft_match = re.search(r'(\d+(?:,\d+)?)\s*(?:sqft|sq\.ft|sq ft|square feet|sft)', details_text, re.IGNORECASE)
                if sqft_match:
                    sqft_str = sqft_match.group(1).replace(',', '')
                    try:
                        sqft = int(sqft_str)
                    except ValueError:
                        sqft = None

            ad_data = {
                "title": title or "Property in Goa",
                "area": area,
                "price_day_inr": price_inr,  # Цена в рупиях
                "price_day_usd": round(price_inr / 83.5, 1) if price_inr > 0 else 0,  # Для совместимости
                "photos": [photo_url] if photo_url else [],
                "owner_type": "private",
                "source": "olx",
                "olx_id": olx_id,
                "olx_url": link,
                "location_raw": location_raw,  # Сохраняем оригинальную локацию для отладки
                "parsed_at": datetime.utcnow().isoformat(),
                "bedrooms": bedrooms,        
                "bathrooms": bathrooms,      
                "sqft": sqft,
            }

            ads.append(ad_data)

        except Exception as e:
            logger.debug(f"Ошибка парсинга одного объявления: {e}")
            continue

    return ads

def sync_parse_olx_full() -> int:
    total_added = 0
    page = 1
    empty_pages_in_row = 0

    logger.info("Запуск парсинга OLX только по северным районам Гоа")

    while True:
        logger.info(f"Парсим страницу {page}...")
        
        html = get_page_html(page)
        if not html:
            logger.warning(f"Страница {page} не загрузилась")
            empty_pages_in_row += 1
            if empty_pages_in_row >= 3:
                break
            time.sleep(5)
            page += 1
            continue

        ads = parse_page(html)

        if not ads:
            logger.info(f"Страница {page}: нет новых объявлений в целевых районах")
            empty_pages_in_row += 1
            if empty_pages_in_row >= 3:
                logger.info("3 пустые страницы подряд — завершение парсинга")
                break
        else:
            empty_pages_in_row = 0
            for ad in ads:
                create_property(ad)
                total_added += 1
                logger.info(f"Добавлено: {ad['title']} ({ad['area']}) — {ad['price_day_inr']} ₹")

        logger.info(f"Страница {page}: добавлено {len(ads)} новых объявлений")
        time.sleep(3)
        page += 1

        if page > 100:
            logger.info("Достигнут лимит в 100 страниц")
            break

    logger.info(f"Парсинг завершен. Добавлено {total_added} новых объектов из целевых районов")
    return total_added

async def parse_olx_listing() -> int:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_parse_olx_full)