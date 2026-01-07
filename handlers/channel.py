# handlers/channel.py — ЛОГИКА КАНАЛА @goa_realt (Январь 2026)

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.firebase_db import (
    create_request,
    add_proposal,
    get_request_status,
    set_request_status,
    get_proposals_by_request,
    get_request,
    get_user_active_requests,  # NEW: Функция для получения активных запросов клиента
    deactivate_old_requests    # NEW: Функция для деактивации старых запросов
)
from utils.keyboards import payment_menu_kb

router = Router()

# === FSM для реалторов — предложение варианта ===
class ProposeStates(StatesGroup):
    waiting_proposal = State()


# === Кнопка "Отправить запрос в канал" из поиска ===
@router.callback_query(F.data == "send_to_channel")
async def send_request_to_channel(call: CallbackQuery):
    user_id = call.from_user.id
    # user_query берём из последнего сообщения (или из FSM — если сохранял в smart_search)
    user_query = call.message.text or "Запрос без текста"

    # NEW: Деактивируем старые активные запросы клиента
    deactivate_old_requests(user_id)

    # Создаём новый запрос в базе
    request_id = create_request(user_id, user_query)

    # Публикуем в канал
    channel_msg = await call.bot.send_message(
        chat_id="@goa_realt",
        text=f"Новый запрос от @{call.from_user.username or 'аноним'} (ID: {request_id})\n\n"
             f"Запрос: {user_query}\n\n"
             f"Реалторы, предлагайте варианты!"
    )

    # Кнопка "Предложить вариант"
    kb = InlineKeyboardBuilder()
    kb.button(text="Предложить вариант", callback_data=f"propose_{request_id}")
    await call.bot.edit_message_reply_markup(
        chat_id="@goa_realt",
        message_id=channel_msg.message_id,
        reply_markup=kb.as_markup()
    )

    # Ссылка на пост
    post_link = f"https://t.me/goa_realt/{channel_msg.message_id}"

    await call.message.answer(
        f"Твой запрос отправлен в канал @goa_realt!\n\n"
        f"ID запроса: {request_id}\n\n"
        f"Смотри здесь: {post_link}\n\n"
        f"Как только реалторы предложат варианты — я пришлю их тебе по 10 штук с кнопкой 'Показать ещё'."
    )
    await call.answer("Запрос отправлен!")


# === Реалтор нажимает "Предложить вариант" в канале ===
@router.callback_query(lambda c: c.data.startswith("propose_"))
async def propose_variant(call: CallbackQuery, state: FSMContext):
    request_id = call.data.split("_")[1]

    # Проверяем, активен ли запрос
    request = get_request(request_id)
    if not request or request["status"] != "active":
        await call.answer("Этот запрос уже неактивен. Предложение не принято.", show_alert=True)
        return

    # Сохраняем request_id в состоянии
    await state.update_data(request_id=request_id)
    await state.set_state(ProposeStates.waiting_proposal)

    # Перебрасываем реалтора в личку бота
    await call.bot.send_message(
        call.from_user.id,
        f"Предложи вариант для запроса ID {request_id}:\n\n"
        "Напиши текст с описанием, ценой, фото (если есть), контактами.\n\n"
        "Я перешлю пользователю анонимно."
    )
    await call.answer("Жду предложение в личке бота!")


# === Реалтор отправляет предложение в личке бота ===
@router.message(ProposeStates.waiting_proposal)
async def receive_proposal(message: Message, state: FSMContext):
    data = await state.get_data()
    request_id = data["request_id"]
    realtor_id = message.from_user.id
    proposal_text = message.text

    # Проверяем статус запроса перед сохранением
    request = get_request(request_id)
    if not request or request["status"] != "active":
        await message.answer("Этот запрос уже неактивен. Предложение не принято.")
        await state.clear()
        return

    # Сохраняем предложение
    add_proposal(request_id, realtor_id, proposal_text)

    # Уведомляем реалтора
    await message.answer("Предложение отправлено пользователю! Спасибо!")

    # Уведомляем пользователя
    user_id = request["user_id"]
    await message.bot.send_message(
        user_id,
        f"Новое предложение по твоему запросу ID {request_id}!\n\n"
        f"От риэлтора: {proposal_text}\n\n"
        f"Если интересно — свяжись с риэлтором через канал @goa_realt"
    )

    await state.clear()


# === Показ предложений пользователю (по 10 с пагинацией) ===
async def show_proposals(message: Message, request_id: str, page: int = 0):
    proposals = get_proposals_by_request(request_id, limit=10, offset=page * 10)

    if not proposals:
        await message.answer("Пока нет предложений по твоему запросу.")
        return

    text = f"<b>Предложения по запросу ID {request_id}:</b>\n\n"
    for i, prop in enumerate(proposals, start=page * 10 + 1):
        text += f"{i}. {prop['proposal_text']}\n\n"

    kb = InlineKeyboardBuilder()
    if len(proposals) == 10:
        kb.button(text="Показать ещё 10", callback_data=f"more_proposals_{request_id}_{page + 1}")

    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")


# === Кнопка "Показать ещё 10 предложений" ===
@router.callback_query(lambda c: c.data.startswith("more_proposals_"))
async def more_proposals(call: CallbackQuery):
    parts = call.data.split("_")
    request_id = parts[2]
    page = int(parts[3])

    await show_proposals(call.message, request_id, page)
    await call.answer()


# === Кнопка "Показать предложения" (добавь в сообщение после отправки запроса) ===
@router.callback_query(lambda c: c.data.startswith("show_proposals_"))
async def show_proposals_handler(call: CallbackQuery):
    request_id = call.data.split("_")[2]
    await show_proposals(call.message, request_id)
    await call.answer()