# bot.py (ФИНАЛЬНАЯ ВЕРСИЯ 4.0)
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
from aiogram.types import LabeledPrice, WebAppInfo, BotCommand, BotCommandScopeChat
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters import Command

# --- Настройки ---
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


# --- Работа с БД ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS categories
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       UNIQUE
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS products
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT,
                       category_id
                       INTEGER,
                       price
                       INTEGER,
                       description
                       TEXT,
                       sizes
                       TEXT,
                       colors
                       TEXT,
                       photo
                       TEXT,
                       stock
                       INTEGER
                       DEFAULT
                       0,
                       created_at
                       TEXT
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pending_orders
                   (
                       payload
                       TEXT
                       PRIMARY
                       KEY,
                       user_id
                       INTEGER,
                       amount
                       INTEGER,
                       created_at
                       TEXT
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       order_number
                       TEXT
                       UNIQUE,
                       user_id
                       INTEGER,
                       payload
                       TEXT,
                       total_amount
                       INTEGER,
                       status
                       TEXT,
                       payment_info
                       TEXT,
                       created_at
                       TEXT
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS order_items
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       order_id
                       INTEGER,
                       product_id
                       INTEGER,
                       name
                       TEXT,
                       size
                       TEXT,
                       color
                       TEXT,
                       unit_price
                       INTEGER,
                       qty
                       INTEGER
                   )""")
    conn.commit()
    conn.close()


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


init_db()


def is_admin(uid): return uid in ADMIN_IDS


def cents_from_decimal(x): return int((Decimal(str(x)) * 100).quantize(Decimal('1')))


class AddProductStates(
    StatesGroup): name = State(); category = State(); price = State(); description = State(); sizes = State(); colors = State(); stock = State(); photo = State()


class EditProductStates(StatesGroup): id_to_edit = State(); field = State(); new_value = State()


class DeleteProductStates(StatesGroup): id_to_delete = State()


class DeleteCategoryStates(StatesGroup): id_to_delete = State()  # Новое состояние для удаления категории


# --- Основные хендлеры ---
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardBuilder()
    web_app_url = 'https://cozn1l.github.io/gorossotestbot1/webapp/'
    kb.row(types.KeyboardButton(text='🏪 Открыть магазин', web_app=WebAppInfo(url=web_app_url)))
    kb.row(types.KeyboardButton(text='Мои заказы'), types.KeyboardButton(text='Контакты'))
    if is_admin(message.from_user.id):
        kb.row(types.KeyboardButton(text='Админ-панель'))
    await message.reply('Привет! Добро пожаловать в Gorosso.', reply_markup=kb.as_markup(resize_keyboard=True))


@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        command = data.get('command')
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


# ... Другие хендлеры (Контакты, Мои заказы, Оплата) здесь без изменений ...
# ...

# --- АДМИН-ПАНЕЛЬ (ПОЛНЫЙ КОД) ---
@dp.message(F.text.in_({'Админ-панель', '/admin'}))
async def admin_menu(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.reply('Админ-панель:', reply_markup=get_admin_keyboard())


@dp.message(F.text == '< Назад в меню')
async def back_to_main_menu(message: types.Message):
    await cmd_start(message)


# -- Добавление, Редактирование, Список товаров --
# ... Все хендлеры для товаров здесь без изменений ...
# ...

# -- Удаление товара --
@dp.message(F.text == 'Удалить товар')
async def delete_product_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.reply('Введите ID товара для удаления:', reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(DeleteProductStates.id_to_delete)


@dp.message(DeleteProductStates.id_to_delete)
async def delete_product_confirm(message: types.Message, state: FSMContext):
    try:
        pid = int(message.text)
        db_exec('DELETE FROM products WHERE id = ?', (pid,))
        await message.reply(f'Товар {pid} удалён.', reply_markup=get_admin_keyboard())
    except ValueError:
        await message.reply('Неверный ID. Введите число.', reply_markup=get_admin_keyboard())
    finally:
        await state.clear()


# === НОВЫЙ КОД: УДАЛЕНИЕ КАТЕГОРИИ ===
@dp.message(F.text == 'Удалить категорию')
async def delete_category_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    categories = db_exec('SELECT id, name FROM categories ORDER BY name', fetch=True)
    if not categories:
        return await message.reply("Категорий для удаления нет.", reply_markup=get_admin_keyboard())

    text = "Какая категория будет удалена? Введите её ID:\n\n"
    for cat in categories:
        text += f"ID: {cat['id']} - {cat['name']}\n"

    await message.reply(text, reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(DeleteCategoryStates.id_to_delete)


@dp.message(DeleteCategoryStates.id_to_delete)
async def delete_category_confirm(message: types.Message, state: FSMContext):
    try:
        cat_id = int(message.text)
        # Проверяем, есть ли товары в этой категории
        products_in_cat = db_exec('SELECT id FROM products WHERE category_id = ?', (cat_id,), fetch=True)
        if products_in_cat:
            await message.reply(
                f"Ошибка: Нельзя удалить категорию, так как в ней есть товары. Сначала удалите или переместите товары.",
                reply_markup=get_admin_keyboard())
        else:
            db_exec('DELETE FROM categories WHERE id = ?', (cat_id,))
            await message.reply(f'Категория с ID {cat_id} удалена.', reply_markup=get_admin_keyboard())
    except ValueError:
        await message.reply('Неверный ID. Введите число.', reply_markup=get_admin_keyboard())
    finally:
        await state.clear()


# Вспомогательная функция для клавиатуры админа
def get_admin_keyboard():
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text='Добавить товар'), types.KeyboardButton(text='Список товаров'))
    kb.row(types.KeyboardButton(text='Редактировать товар'), types.KeyboardButton(text='Удалить товар'))
    kb.row(types.KeyboardButton(text='Удалить категорию'))  # Новая кнопка
    kb.row(types.KeyboardButton(text='< Назад в меню'))
    return kb.as_markup(resize_keyboard=True)


# --- ЗАПУСК ---
async def main():
    logger.info('Starting Gorosso bot...')
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.warning('Bot stopped.')