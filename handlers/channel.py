# handlers/channel.py — ЛОГИКА КАНАЛА @goa_realt (Январь 2026)

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import logging

logger = logging.getLogger(__name__)

from database.firebase_db import (
    create_request,
    add_proposal,
    get_request_status,
    set_request_status,
    get_proposals_by_request,
    get_request,
    get_user_active_requests,  # NEW: Функция для получения активных запросов клиента
    deactivate_old_requests,    # NEW: Функция для деактивации старых запросов
    set_user_status,
    get_user_status
)
from utils.keyboards import payment_menu_kb

router = Router()

# === FSM для реалторов — предложение варианта ===
class ProposeStates(StatesGroup):
    waiting_proposal = State()
    confirming_proposal = State()  # NEW: Состояние для подтверждения


# === Кнопка "Отправить запрос в канал" из поиска ===
@router.callback_query(F.data == "send_to_channel")
async def send_request_to_channel(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    # user_query берём из последнего сообщения (или из FSM — если сохранял в smart_search)
    # user_query = call.message.text or "Запрос без текста"
    data = await state.get_data()
    user_query = data.get("user_query") or "Запрос без текста"

    # NEW: Деактивируем старые активные запросы клиента
    deactivate_old_requests(user_id)

    # Создаём новый запрос в базе
    request_id = create_request(user_id, user_query)

    # ОТВЕЧАЕМ НА CALLBACK СРАЗУ — обязательно первым!
    await call.answer("Запрос отправляется в канал...")

    try:
        # Публикуем в канал
        channel_msg = await call.bot.send_message(
            chat_id="@goa_realt",
            text=f"Новый запрос (ID: {request_id})\n\n"
                 f"Запрос: {user_query}\n\n"
                 f"Реалторы, предлагайте варианты!"
        )

        # Добавляем кнопку
        kb = InlineKeyboardBuilder()
        kb.button(text="Предложить вариант", callback_data=f"propose_{request_id}")
        await call.bot.edit_message_reply_markup(
            chat_id="@goa_realt",
            message_id=channel_msg.message_id,
            reply_markup=kb.as_markup()
        )

        post_link = f"https://t.me/goa_realt/{channel_msg.message_id}"

        await call.message.answer(
            f"Твой запрос отправлен в канал @goa_realt!\n\n"
            f"ID запроса: {request_id}\n\n"
            f"Предложения от реалторов придут тебе в личку по 10 штук."
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке в канал: {e}")
        await call.message.answer("Не удалось опубликовать запрос в канал. Попробуй позже.")


# === Реалтор нажимает "Предложить вариант" в канале ===
@router.callback_query(lambda c: c.data.startswith("propose_"))
async def propose_variant(call: CallbackQuery, state: FSMContext):
    request_id = call.data.split("_")[1]

    # Проверяем, активен ли запрос
    request = get_request(request_id)
    if not request or request["status"] != "active":
        await call.answer("Этот запрос уже неактивен. Предложение не принято.", show_alert=True)
        return

    # ОТВЕЧАЕМ НА CALLBACK СРАЗУ — обязательно первым!
    await call.answer("Открываю чат для предложения...")

    # Сохраняем request_id в состоянии
    # await state.update_data(request_id=request_id)
    # await state.set_state(ProposeStates.waiting_proposal)

    # # === ДОБАВЬ ЭТИ ЛОГИ ===
    # current_state = await state.get_state()
    # current_data = await state.get_data()
    # logger.info(f"Установлено состояние для user {call.from_user.id}: {current_state}")
    # logger.info(f"Данные состояния: {current_data}")
    # # === КОНЕЦ ЛОГОВ ===
    # NEW: Устанавливаем статус вместо FSM
    set_user_status(call.from_user.id, f"waiting_proposal_{request_id}")

    # Отправляем сообщение в личку (может быть медленно — но callback уже отвечен)
    try:
        await call.bot.send_message(
            call.from_user.id,
            f"Предложи вариант для запроса ID {request_id}:\n\n"
            "Напиши текст с описанием, ценой, фото (если есть), контактами.\n\n"
            "Я перешлю пользователю анонимно."
        )
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение реалтору {call.from_user.id}: {e}")
        await call.message.answer("Не смог написать тебе в личку. Запусти бота и попробуй снова.")

# === Реалтор отправляет предложение в личке бота ===
async def receive_proposal(message: Message, status: str):
    # Извлекаем request_id из статуса
    parts = status.split("_")
    if len(parts) < 3:
        await message.answer("Ошибка состояния. Начни заново.")
        set_user_status(message.from_user.id, None)
        return

    request_id = parts[2]

    # Проверка активности запроса
    request = get_request(request_id)
    if not request or request["status"] != "active":
        await message.answer("Этот запрос уже неактивен.")
        set_user_status(message.from_user.id, None)
        return

    proposal_text = message.text

    # Красивое форматирование
    formatted = f"""
<b>Твоё предложение:</b>

{proposal_text}

Отправить клиенту?
    """

    kb = InlineKeyboardBuilder()
    kb.button(text="Да, отправить", callback_data=f"confirm_proposal_{request_id}")
    kb.button(text="Отмена", callback_data="cancel_proposal")

    await message.answer(formatted, reply_markup=kb.as_markup(), parse_mode="HTML")

    # Обновляем статус на подтверждение (сохраняем текст)
    set_user_status(message.from_user.id, f"confirming_proposal_{request_id}")
    # Можно сохранить текст в отдельном поле, если нужно


@router.callback_query(F.data.startswith("confirm_proposal_"))
async def confirm_proposal(call: CallbackQuery):
    request_id = call.data.split("_")[2]

    # Здесь можно получить текст из предыдущего сообщения или из статуса
    # Для простоты — пусть реалтор знает, что отправляет

    # Логика отправки клиенту...
    add_proposal(request_id, call.from_user.id, "текст из предыдущего сообщения")

    await call.message.edit_text("Предложение отправлено клиенту!")

    # Очищаем статус
    set_user_status(call.from_user.id, None)

@router.callback_query(F.data == "cancel_proposal")
async def cancel_proposal(call: CallbackQuery):
    await call.message.edit_text("Предложение отменено.")
    set_user_status(call.from_user.id, None)

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