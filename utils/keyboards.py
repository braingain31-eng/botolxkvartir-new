from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def start_kb() -> ReplyKeyboardMarkup:
    """
    Главное меню — всегда видно рядом с полем ввода (aiogram 3.x)
    """
    buttons = [
        [KeyboardButton(text="Голосом"), KeyboardButton(text="Текстом")],
        [KeyboardButton(text="Топ-10 до $500"), KeyboardButton(text="Все варианты")],
        [KeyboardButton(text="Для риэлторов")]
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,           # ← ОБЯЗАТЕЛЬНО передаём список рядов
        resize_keyboard=True,
        one_time_keyboard=False,    # не исчезает после нажатия
        row_width=2
    )


# === 2. Быстрые фильтры (самые популярные запросы в Гоа) ===
def quick_filters_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Anjuna", callback_data="filter_area_anjuna")
    kb.button(text="Vagator", callback_data="filter_area_vagator")
    kb.button(text="Arpora / Baga", callback_data="filter_area_arpora")
    kb.button(text="Candolim / Calangute", callback_data="filter_area_candolim")
    kb.button(text="Morjim / Ashvem", callback_data="filter_area_morjim")
    kb.button(text="С бассейном", callback_data="filter_pool")
    kb.button(text="До $100/ночь", callback_data="filter_price_100")
    kb.button(text="Вилла 3+ спальни", callback_data="filter_villa_3bhk")
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()


# === 3. Пагинация (для списка результатов) ===
def pagination_kb(page: int = 1, total_pages: int = 1, prefix: str = "page"):
    """
    prefix — например: "search", "my_props", "top10"
    """
    kb = InlineKeyboardBuilder()

    if page > 1:
        kb.button(text="◀ Назад", callback_data=f"{prefix}_prev_{page-1}")

    kb.button(text=f"{page}/{total_pages}", callback_data="current_page")

    if page < total_pages:
        kb.button(text="Вперёд ▶", callback_data=f"{prefix}_next_{page+1}")

    kb.adjust(3 if page > 1 and page < total_pages else 2 if page == 1 or page == total_pages else 1)
    return kb.as_markup()


# === 4. Клавиатура под карточкой объекта ===
def property_detail_kb(prop_id: str, is_paid: bool = False):
    kb = InlineKeyboardBuilder()
    kb.button(text="Детальнее", callback_data=f"detail_{prop_id}")

    if is_paid:
        kb.button(text="Контакты хозяина", callback_data=f"contact_{prop_id}")
    else:
        kb.button(text="Получить контакты ($10)", callback_data="show_payment")

    kb.button(text="Ещё варианты", callback_data="new_search")
    kb.adjust(1)
    return kb.as_markup()


# === 5. После показа контактов ===
def after_contact_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад к объекту", callback_data="back_to_prop")
    kb.button(text="Новый поиск", callback_data="new_search")
    kb.adjust(1)
    return kb.as_markup()


# === 6. Оплатить или позже ===
def pay_or_later_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Оплатить доступ ($10/неделя)", callback_data="show_payment")
    kb.button(text="Позже", callback_data="later")
    kb.adjust(1)
    return kb.as_markup()


# === 7. Меню выбора способа оплаты ===
def payment_menu_kb():
    kb = InlineKeyboardBuilder()

    kb.row(
        InlineKeyboardButton(text="Карта → 7 дней ($10)", callback_data="pay_card_7"),
        InlineKeyboardButton(text="Карта → 30 дней ($20)", callback_data="pay_card_30")
    )
    kb.row(
        InlineKeyboardButton(text="TON → 7 дней", callback_data="pay_crypto_7_ton"),
        InlineKeyboardButton(text="TON → 30 дней", callback_data="pay_crypto_30_ton")
    )
    kb.row(
        InlineKeyboardButton(text="USDT → 7 дней", callback_data="pay_crypto_7_usdt"),
        InlineKeyboardButton(text="USDT → 30 дней", callback_data="pay_crypto_30_usdt")
    )
    kb.row(
        InlineKeyboardButton(text="1000 Stars → 7 дней", callback_data="pay_stars_7"),
        InlineKeyboardButton(text="2000 Stars → 30 дней", callback_data="pay_stars_30")
    )
    kb.button(text="Назад", callback_data="back_to_search")
    kb.adjust(1)
    return kb.as_markup()


# === 8. Риэлторское меню ===
def agent_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Добавить объект", callback_data="start_add_property")
    kb.button(text="Мои объекты", callback_data="my_properties")
    kb.button(text="Статистика и бонус", callback_data="agent_stats")
    kb.adjust(1)
    return kb.as_markup()


# === 9. Подтверждение публикации объекта ===
def confirm_publish_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Опубликовать", callback_data="confirm_publish")
    kb.button(text="Отменить", callback_data="cancel_publish")
    kb.adjust(2)
    return kb.as_markup()


# === 10. Сортировка и фильтры в результатах ===
def sort_and_filter_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="По цене ↑", callback_data="sort_price_asc")
    kb.button(text="По цене ↓", callback_data="sort_price_desc")
    kb.button(text="Т6олько частники", callback_data="filter_private")
    kb.button(text="Только риэлторы", callback_data="filter_agent")
    kb.button(text="Быстрые фильтры", callback_data="quick_filters")
    kb.button(text="Сбросить всё", callback_data="reset_filters")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


# === 11. Простая кнопка "Назад" ===
def back_kb(callback_data: str = "back"):
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад", callback_data=callback_data)
    return kb.as_markup()