import asyncio
import logging
import random
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, PreCheckoutQuery, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import sys

# 🌐 ДЛЯ RENDER: добавляем веб-сервер чтобы порт был открыт
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# ⚡ ТОКЕН БЕРИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ НА RENDER
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8712837824:AAGBe3oRWVeP_Rq-RYaLm21xGYTOglku980")

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Файлы для хранения данных (на Render лучше использовать /tmp или БД)
USERS_FILE = "/tmp/users.json"
CHATS_FILE = "/tmp/chats.json"
QUEUE_FILE = "/tmp/queue.json"

# Цены в звездах
PREMIUM_PRICES = {
    "1day": 50,    
    "7days": 129,  
    "30days": 249  
}

# Состояния
class ChatStates(StatesGroup):
    in_chat = State()
    waiting = State()
    selecting_gender = State()

# --- Функции для работы с пользователями ---
def load_json(filename, default):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Базы данных
users = load_json(USERS_FILE, {})  
active_chats = load_json(CHATS_FILE, {})  
waiting_queue = load_json(QUEUE_FILE, [])  

def get_user(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {
            "premium_until": None,
            "gender": None,
            "search_count": 0,
            "refs": [],
            "referrer": None,
            "joined_at": datetime.now().isoformat()
        }
        save_json(USERS_FILE, users)
    return users[user_id]

def check_premium(user_id):
    user = get_user(user_id)
    if not user["premium_until"]:
        return False
    try:
        premium_date = datetime.fromisoformat(user["premium_until"])
        return premium_date > datetime.now()
    except:
        return False

def add_premium(user_id, days):
    user = get_user(user_id)
    if user["premium_until"]:
        try:
            current = datetime.fromisoformat(user["premium_until"])
            if current < datetime.now():
                current = datetime.now()
        except:
            current = datetime.now()
    else:
        current = datetime.now()
    
    new_date = current + timedelta(days=days)
    user["premium_until"] = new_date.isoformat()
    save_json(USERS_FILE, users)
    return new_date

def can_search_by_gender(user_id):
    if check_premium(user_id):
        return True
    user = get_user(user_id)
    return user["search_count"] < 1

def use_gender_search(user_id):
    user = get_user(user_id)
    user["search_count"] += 1
    save_json(USERS_FILE, users)

# --- Клавиатуры ---
def get_main_keyboard(user_id):
    is_premium = check_premium(user_id)
    premium_text = "👑 Премиум подписка 🎁" if not is_premium else "👑 Premium активен"
    
    buttons = [
        [InlineKeyboardButton(text="🔍 Найти", callback_data="search_menu")],
        [InlineKeyboardButton(text="🎲 Случайный", callback_data="search_random"),
         InlineKeyboardButton(text="🎯 Найти", callback_data="search_by_gender")],
        [InlineKeyboardButton(text=premium_text, callback_data="premium_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_premium_keyboard():
    buttons = [
        [InlineKeyboardButton(text=f"⭐ 1 день - {PREMIUM_PRICES['1day']} ★", callback_data="premium_1day")],
        [InlineKeyboardButton(text=f"⭐ 7 дней - {PREMIUM_PRICES['7days']} ★", callback_data="premium_7days")],
        [InlineKeyboardButton(text=f"⭐ 30 дней - {PREMIUM_PRICES['30days']} ★", callback_data="premium_30days")],
        [InlineKeyboardButton(text="◀️ Меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_gender_keyboard():
    buttons = [
        [InlineKeyboardButton(text="👨 Парень", callback_data="search_gender_m")],
        [InlineKeyboardButton(text="👩 Девушка", callback_data="search_gender_f")],
        [InlineKeyboardButton(text="◀️ Меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_chat_keyboard():
    buttons = [
        [InlineKeyboardButton(text="⏭️ /next", callback_data="next_chat")],
        [InlineKeyboardButton(text="⏹️ /stop", callback_data="stop_chat")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_ref_keyboard():
    buttons = [
        [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral")],
        [InlineKeyboardButton(text="◀️ Меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Обработчики команд ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    get_user(user_id)
    
    text = (
        f"# Radius | Анонимный...\n\n"
        f"Добро пожаловать в анонимный чат\n"
        f"Выбери действие:"
    )
    
    await message.answer(text, reply_markup=get_main_keyboard(user_id))

@dp.message(Command("search"))
async def cmd_search(message: Message):
    user_id = str(message.from_user.id)
    
    if str(user_id) in active_chats:
        await message.answer("Ты уже в диалоге. Используй /stop чтобы завершить")
        return
    
    if str(user_id) not in [w["user_id"] for w in waiting_queue]:
        waiting_queue.append({"user_id": str(user_id), "gender": None, "type": "random"})
        save_json(QUEUE_FILE, waiting_queue)
        await message.answer("🔍 Ищем собеседника...")
        await try_match_users()
    else:
        await message.answer("Ты уже в очереди поиска")

@dp.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        
        try:
            await bot.send_message(
                int(partner_id),
                "👋 Собеседник покинул чат\n/search - начать поиск",
                reply_markup=get_main_keyboard(int(partner_id))
            )
        except:
            pass
        
        del active_chats[user_id]
        if partner_id in active_chats:
            del active_chats[partner_id]
        save_json(CHATS_FILE, active_chats)
        
        await message.answer("Диалог остановлен\n/search - начать поиск", reply_markup=get_main_keyboard(int(user_id)))
        await state.clear()
    else:
        await message.answer("Ты не в диалоге")

@dp.message(Command("next"))
async def cmd_next(message: Message, state: FSMContext):
    await cmd_stop(message, state)
    await cmd_search(message)

@dp.message(Command("ref"))
async def cmd_ref(message: Message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    
    text = (
        f"👥 Реферальная программа\n\n"
        f"Пригласи друга и получи доступ к поиску по полу\n"
        f"Твоя ссылка: {ref_link}\n\n"
        f"Приглашено: {len(get_user(user_id)['refs'])}"
    )
    
    await message.answer(text, reply_markup=get_ref_keyboard())

# --- Обработчики колбэков ---
@dp.callback_query(F.data == "search_menu")
async def search_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Выбери тип поиска:", reply_markup=get_main_keyboard(callback.from_user.id))

@dp.callback_query(F.data == "search_random")
async def search_random(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    
    if user_id in active_chats:
        await callback.message.edit_text("Ты уже в диалоге. Используй /stop")
        return
    
    waiting_queue.append({"user_id": user_id, "gender": None, "type": "random"})
    save_json(QUEUE_FILE, waiting_queue)
    await callback.message.edit_text("🔍 Нашли кое-кого для тебя...")
    await try_match_users()

@dp.callback_query(F.data == "search_by_gender")
async def search_by_gender(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if can_search_by_gender(user_id):
        await callback.message.edit_text("Выбери пол собеседника:", reply_markup=get_gender_keyboard())
    else:
        text = (
            f"Чтобы продолжить поиск по полу, пригласи (/ref) ещё 1 пользователя в чат "
            f"или оформи премиум-подписку 👏 всего за {PREMIUM_PRICES['1day']} ⭐!"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Премиум подписка 🎁", callback_data="premium_menu")],
            [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("search_gender_"))
async def process_gender_search(callback: CallbackQuery):
    await callback.answer()
    gender = callback.data.split("_")[2]
    user_id = str(callback.from_user.id)
    
    if user_id in active_chats:
        await callback.message.edit_text("Ты уже в диалоге")
        return
    
    if not check_premium(user_id):
        use_gender_search(user_id)
    
    waiting_queue.append({"user_id": user_id, "gender": gender, "type": "gender"})
    save_json(QUEUE_FILE, waiting_queue)
    await callback.message.edit_text("🔍 Ищем по полу...")
    await try_match_users()

@dp.callback_query(F.data == "premium_menu")
async def premium_menu(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if check_premium(user_id):
        user = get_user(user_id)
        until = datetime.fromisoformat(user["premium_until"]).strftime("%d.%m.%Y")
        text = (
            f"👑 Premium активен\n"
            f"Действует до: {until}\n\n"
            f"Преимущества:\n"
            f"- Никакой рекламы\n"
            f"- Первое место в поиске\n"
            f"- Неограниченный поиск по полу"
        )
    else:
        text = (
            f"Премиум подписка 🎁\n\n"
            f"Преимущества:\n"
            f"- Никакой рекламы\n"
            f"- Первое место в поиске\n"
            f"- Неограниченный поиск по полу\n\n"
            f"Выбери продолжительность:"
        )
    
    await callback.message.edit_text(text, reply_markup=get_premium_keyboard())

@dp.callback_query(F.data.startswith("premium_"))
async def process_premium(callback: CallbackQuery):
    await callback.answer()
    period = callback.data.split("_")[1]
    
    if period == "1day":
        days = 1
        price = PREMIUM_PRICES["1day"]
    elif period == "7days":
        days = 7
        price = PREMIUM_PRICES["7days"]
    elif period == "30days":
        days = 30
        price = PREMIUM_PRICES["30days"]
    else:
        return
    
    prices = [LabeledPrice(label=f"Premium {days} дней", amount=price)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Premium {days} дней",
        description=f"Премиум подписка на {days} дней",
        payload=f"premium_{days}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="premium"
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    days = int(payload.split("_")[1])
    user_id = message.from_user.id
    
    until = add_premium(user_id, days)
    
    await message.answer(
        f"✅ Premium активирован до {until.strftime('%d.%m.%Y')}\n"
        f"Спасибо за поддержку!",
        reply_markup=get_main_keyboard(user_id)
    )

@dp.callback_query(F.data == "next_chat")
async def next_chat(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await cmd_stop(callback.message, state)
    await cmd_search(callback.message)

@dp.callback_query(F.data == "stop_chat")
async def stop_chat(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await cmd_stop(callback.message, state)

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Меню:", reply_markup=get_main_keyboard(callback.from_user.id))

@dp.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery):
    await callback.answer()
    await cmd_ref(callback.message)

# --- Функция поиска пар ---
async def try_match_users():
    global waiting_queue, active_chats
    
    if len(waiting_queue) < 2:
        return
    
    queue = list(waiting_queue)
    premium_users = [u for u in queue if check_premium(int(u["user_id"]))]
    regular_users = [u for u in queue if not check_premium(int(u["user_id"]))]
    
    new_queue = premium_users + regular_users
    matched = []
    
    i = 0
    while i < len(new_queue) - 1:
        user1 = new_queue[i]
        user2 = new_queue[i + 1]
        
        if user1["gender"] and user2["gender"]:
            if user1["gender"] != user2["gender"]:
                i += 1
                continue
        
        active_chats[user1["user_id"]] = user2["user_id"]
        active_chats[user2["user_id"]] = user1["user_id"]
        matched.extend([user1["user_id"], user2["user_id"]])
        
        await notify_chat_start(user1["user_id"], user2["user_id"])
        await notify_chat_start(user2["user_id"], user1["user_id"])
        
        i += 2
    
    waiting_queue = [u for u in new_queue if u["user_id"] not in matched]
    save_json(QUEUE_FILE, waiting_queue)
    save_json(CHATS_FILE, active_chats)

async def notify_chat_start(user_id, partner_id):
    try:
        text = (
            f"Нашли кое-кого для тебя\n"
            f"/stop - остановить диалог"
        )
        await bot.send_message(int(user_id), text, reply_markup=get_chat_keyboard())
    except:
        pass

# --- Обработка сообщений в чате ---
@dp.message()
async def handle_chat_message(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        
        user = get_user(user_id)
        gender_emoji = "👨" if user["gender"] == "m" else "👩" if user["gender"] == "f" else ""
        
        try:
            await bot.send_message(
                int(partner_id),
                f"{gender_emoji} {message.text}",
                reply_markup=get_chat_keyboard()
            )
        except:
            await cmd_stop(message, state)

# ===== 🌐 ВЕБ-СЕРВЕР ДЛЯ RENDER =====
async def handle_health(request):
    """Просто отвечаем что бот живой"""
    return web.Response(text="Бот Radius работает 🚀")

async def run_web_server():
    """Запускаем минимальный веб-сервер на порту 10000"""
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Веб-сервер запущен на порту {port}")

async def main():
    """Главная функция запуска"""
    # Запускаем веб-сервер в фоне
    asyncio.create_task(run_web_server())
    
    # Запускаем бота
    logger.info("🚀 Бот Radius запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
