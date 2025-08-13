# bot.py (исправленная и упрощенная версия)
import os
import sqlite3
import uuid
import logging
import asyncio
import json
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import LabeledPrice, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters import Command

# --- Все настройки и хелперы остаются без изменений ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gorosso.db")
load_dotenv(os.path.join(BASE_DIR, 'tokens.env'))
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
CURRENCY = os.getenv("CURRENCY", "MDL")
ADMIN_IDS = [int(x) for x in (os.getenv("ADMIN_IDS", "") or "").split(",") if x.strip()]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


def init_db():
    # ... Ваша функция init_db без изменений ...
    pass


def db_exec(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    cur = conn.cursor()
    cur.execute(query, params)
    if fetch:
        rows = cur.fetchall();
        conn.close();
        return rows
    conn.commit();
    conn.close()


init_db()  # Убедитесь, что эта функция вызывается


# ---------- Helpers (Вспомогательные функции) ----------
def is_admin(uid):
    return uid in ADMIN_IDS


def cents_from_decimal(x):
    if isinstance(x, Decimal):
        a = x
    else:
        a = Decimal(str(x))
    return int((a * 100).quantize(Decimal('1')))


def generate_order_number():
    now = datetime.utcnow()
    # Эта функция для SQLite требует явного указания словаря, поэтому я её немного изменил
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (f"{now.date()}%",))
    count = cur.fetchone()[0]
    conn.close()

    serial = (count if count else 0) + 1
    return f"GRS-{now.strftime('%Y%m%d')}-{serial:04d}"


# Функция для генерации PDF, она понадобится при успешной оплате
def generate_invoice_pdf(order_number, username, items, total_amount):
    # Здесь должен быть твой код для генерации PDF.
    # Если он не нужен, можно оставить эту функцию пустой.
    logger.info(f"Generated PDF for order {order_number}")
    pass  # Временно, чтобы не было ошибки


# ... Все остальные хелперы (is_admin, generate_order_number и т.д.) без изменений ...

class AddProductStates(
    StatesGroup): name = State(); category = State(); price = State(); description = State(); sizes = State(); colors = State(); stock = State(); photo = State()


class EditProductStates(StatesGroup): id_to_edit = State(); field = State(); new_value = State()


class DeleteProductStates(StatesGroup): id_to_delete = State()


# --- Основные хендлеры ---

@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardBuilder()
    # !!! ЗАМЕНИТЬ НА СВОЙ РЕАЛЬНЫЙ URL от GitHub Pages !!!
    web_app_url = 'https://cozn1l.github.io/gorossotestbot/webapp/'
    kb.row(types.KeyboardButton(text='🏪 Открыть магазин', web_app=WebAppInfo(url=web_app_url)))
    kb.row(types.KeyboardButton(text='Мои заказы'), types.KeyboardButton(text='Контакты'))
    if is_admin(message.from_user.id):
        kb.row(types.KeyboardButton(text='/admin'))
    await message.reply('Привет! Добро пожаловать в Gorosso.', reply_markup=kb.as_markup(resize_keyboard=True))


@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message):
    """
    Этот хендлер теперь принимает ТОЛЬКО заказ на оплату.
    """
    try:
        data = json.loads(message.web_app_data.data)
        command = data.get('command')
        logger.info(f"Received from WebApp: {command}")

        if command == 'create_order':
            cart_data = data.get('cart', {})
            if not cart_data: return

            uid = message.from_user.id
            prices = []
            total_amount = 0
            for key, cart_item in cart_data.items():
                item = cart_item['item']
                qty = cart_item['qty']
                price_cents = int(item['price']) * qty
                total_amount += price_cents
                prices.append(LabeledPrice(label=f"{item['name']} x{qty}", amount=price_cents))

            payload = str(uuid.uuid4())
            db_exec('INSERT INTO pending_orders (payload, user_id, amount, created_at) VALUES (?, ?, ?, ?)',
                    (payload, uid, total_amount, datetime.utcnow().isoformat()))

            await bot.send_invoice(
                chat_id=uid, title='Оплата заказа Gorosso', description='Оплата товаров из корзины',
                provider_token=PROVIDER_TOKEN, currency=CURRENCY, prices=prices, payload=payload
            )

    except Exception as e:
        logger.error(f"Error in web_app_data_handler: {e}", exc_info=True)


@dp.message(F.text == 'Контакты')
async def contacts(message: types.Message):
    await message.reply('Gorosso — streetwear brand\nСайт: gorosso.com\nInstagram: @gorosso')


@dp.message(F.text == 'Мои заказы')
async def my_orders(message: types.Message):
    # ... Ваша функция my_orders без изменений ...
    pass


# --- ПЛАТЕЖНАЯ ЛОГИКА (БЕЗ ИЗМЕНЕНИЙ) ---
@dp.pre_checkout_query()
async def precheckout_handler(pre_q: types.PreCheckoutQuery):
    # ... Ваш код ...
    pass


@dp.message(F.content_type == types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: types.Message):
    # ... Ваш код ...
    pass


# --- АДМИН-ПАНЕЛЬ (БЕЗ ИЗМЕНЕНИЙ) ---
# Все ваши админские хендлеры остаются здесь как есть
@dp.message(Command('admin'))
async def admin_menu(message: types.Message):
    # ... Ваш код ...
    pass


# ... и все остальные ...


# --- ЗАПУСК ---
async def main():
    logger.info('Starting Gorosso bot...')
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.warning('Bot stopped.')