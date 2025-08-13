# api.py
import os
import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Настройки и подключение к той же БД, что и у бота ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gorosso.db")

app = FastAPI()

# Разрешаем запросы из любого источника (важно для Web App)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def db_exec_api(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


@app.get("/api/all_data")
def get_all_data():
    """
    Этот эндпоинт будет вызываться из JavaScript при загрузке магазина.
    Он отдает все категории и все товары одним запросом.
    """
    try:
        categories = db_exec_api('SELECT id, name FROM categories ORDER BY name', fetch=True)
        products = db_exec_api(
            'SELECT id, name, category_id, price, description, sizes, colors, photo, stock FROM products', fetch=True)

        # Преобразуем строки с размерами и цветами в списки для удобства JS
        for p in products:
            p['sizes'] = [s.strip() for s in (p.get('sizes') or '').split(',') if s.strip()]
            p['colors'] = [c.strip() for c in (p.get('colors') or '').split(',') if c.strip()]

        return {
            'categories': categories,
            'products': products
        }
    except Exception as e:
        return {"error": str(e)}

# Чтобы запустить этот API локально для теста:
# 1. Установи fastapi и uvicorn: pip install fastapi "uvicorn[standard]"
# 2. В терминале выполни команду: uvicorn api:app --reload