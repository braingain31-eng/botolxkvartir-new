# handlers/agent.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.firebase_db import get_user, create_or_update_user, create_agent_property
from utils.agent_utils import increment_agent_property_count
# from utils.keyboards import InlineKeyboardMarkup  # если используешь где-то

router = Router()


# === Состояния для добавления объекта риэлтором ===
class AddPropertyStates(StatesGroup):
    waiting_title = State()
    waiting_params = State()      # цена, район, спальни, гости
    waiting_photos = State()
    waiting_description = State()
    waiting_confirmation = State()


# === Регистрация как риэлтор ===
@router.message(F.text == "/register_agent")
async def register_agent(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if user and user.get("user_type") == "agent":
        await message.answer("Вы уже зарегистрированы как риэлтор!")
        return

    create_or_update_user(user_id, user_type="agent")
    await message.answer(
        "Вы успешно зарегистрированы как риэлтор!\n\n"
        "Добавьте 5 объектов за неделю — получите **7 дней премиум-доступа бесплатно**\n"
        "Ваши объекты будут в приоритете в поиске.\n\n"
        "Чтобы добавить объект → нажмите /add_property"
    )


# === Меню риэлтора ===
@router.callback_query(F.data == "agent_menu")
async def agent_menu(call: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="Добавить объект", callback_data="start_add_property")
    kb.button(text="Мои объекты", callback_data="my_properties")
    kb.button(text="Статистика", callback_data="agent_stats")
    kb.adjust(1)

    await call.message.edit_text(
        "Риэлторское меню\n\n"
        "Добавьте 5 объектов за неделю → +7 дней премиум бесплатно!",
        reply_markup=kb.as_markup()
    )
    await call.answer()


# === Начало добавления объекта ===
@router.callback_query(F.data == "start_add_property")
@router.message(F.text == "/add_property")
async def start_add_property(message: Message | CallbackQuery, state: FSMContext):
    if isinstance(message, CallbackQuery):
        await message.message.edit_text("1/5 — Название объекта (например: Villa Sunset 3BHK)")
        await message.answer()
    else:
        await message.answer("1/5 — Название объекта (например: Villa Sunset 3BHK)")

    await state.set_state(AddPropertyStates.waiting_title)


# === Шаг 1: Название ===
@router.message(AddPropertyStates.waiting_title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer(
        "2/5 — Параметры через запятую:\n"
        "Пример: 120, Anjuna, 3 спальни, 6 гостей"
    )
    await state.set_state(AddPropertyStates.waiting_params)


# === Шаг 2: Параметры ===
@router.message(AddPropertyStates.waiting_params)
async def process_params(message: Message, state: FSMContext):
    text = message.text.strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 4:
        await message.answer("Неверный формат. Пример: 120, Anjuna, 3 спальни, 6 гостей")
        return

    try:
        price_day = float(parts[0])
    except ValueError:
        await message.answer("Цена должна быть числом (USD в сутки)")
        return

    await state.update_data(
        price_day=price_day,
        area=parts[1],
        bedrooms=parts[2],
        guests=int(parts[3])
    )
    await message.answer("3/5 — Пришлите до 4 фото объекта (или напишите «без фото»)")
    await state.set_state(AddPropertyStates.waiting_photos)


# === Шаг 3: Фото ===
@router.message(AddPropertyStates.waiting_photos, F.photo | F.text)
async def process_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    if message.text and message.text.lower() == "без фото":
        await state.update_data(photos=[])
        await message.answer("4/5 — Описание объекта (удобства, мин. срок, даты и т.д.):")
        await state.set_state(AddPropertyStates.waiting_description)
        return

    if message.photo:
        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)

        if len(photos) >= 4:
            await message.answer("Фото принято! (4/4)\n\n4/5 — Описание объекта:")
            await state.set_state(AddPropertyStates.waiting_description)
        else:
            await message.answer(f"Фото принято ({len(photos)}/4). Отправьте ещё или напишите «готово»")
        return

    if message.text and message.text.lower() == "готово":
        await message.answer("4/5 — Описание объекта:")
        await state.set_state(AddPropertyStates.waiting_description)


# === Шаг 4: Описание ===
@router.message(AddPropertyStates.waiting_description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())

    data = await state.get_data()
    photos_count = len(data.get("photos", []))

    preview = (
        f"Подтвердите объект:\n\n"
        f"Название: {data['title']}\n"
        f"Цена: ${data['price_day']}/ночь\n"
        f"Район: {data['area']}\n"
        f"Спальни: {data['bedrooms']}\n"
        f"Гостей: {data['guests']}\n"
        f"Фото: {photos_count}\n"
        f"Описание: {data['description'][:100]}{'...' if len(data['description']) > 100 else ''}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="Опубликовать", callback_data="confirm_publish")
    kb.button(text="Отмена", callback_data="cancel_publish")
    kb.adjust(1)

    await message.answer(preview, reply_markup=kb.as_markup())
    await state.set_state(AddPropertyStates.waiting_confirmation)


# === Подтверждение публикации ===
@router.callback_query(F.data == "confirm_publish")
async def confirm_publish(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = call.from_user.id

    # Сохраняем объект в Firebase
    prop_id, bonus_given = create_agent_property(user_id, {
        "title": data["title"],
        "price_day": data["price_day"],
        "area": data["area"],
        "bedrooms": data["bedrooms"],
        "guests": data["guests"],
        "photos": data.get("photos", []),
        "description": data["description"],
        "owner_type": "agent",
        "status": "active"
    })

    # Обновляем счётчик и проверяем бонус
    current_count, _ = increment_agent_property_count(user_id)

    text = f"Объект успешно опубликован!\nID: <code>{prop_id}</code>\n\nДобавлено на этой неделе: <b>{current_count}/5</b>"

    if bonus_given:
        text += "\n\nБОНУС АКТИВИРОВАН!\n+7 дней премиум-доступа бесплатно!"

    await call.message.edit_text(text, parse_mode="HTML")
    await state.clear()
    await call.answer()


# === Отмена ===
@router.callback_query(F.data.in_({"cancel_publish", "cancel_add"}))
async def cancel_publish(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Добавление объекта отменено.")
    await state.clear()
    await call.answer()