import asyncio
import random
import os
import aiosqlite
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8756762893:AAHAApb8Fo50pj-gju38kk45tvOJiPtD314" 
# Твоя постоянная ссылка от Render
WEBAPP_URL = "https://kazik2-1.onrender.com" 

# --- FASTAPI ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "game.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 100.0
            )
        """)
        await db.commit()

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# Эндпоинт для получения баланса при загрузке страницы
@app.get("/api/balance")
async def get_balance(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 100.0))
                await db.commit()
                return {"balance": 100.0}
            return {"balance": row[0]}

@app.post("/api/upgrade")
async def process_upgrade(request: Request):
    data = await request.json()
    chance = data.get("chance", 50)
    bet = data.get("bet", 10)
    user_id = data.get("user_id")

    if not user_id:
        raise HTTPException(status_code=400, detail="No user_id")

    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем баланс
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 100.0))
                await db.commit()
                current_balance = 100.0
            else:
                current_balance = row[0]

        # Проверка баланса
        if current_balance < bet:
            return {"win": False, "error": "Недостаточно средств", "new_balance": current_balance}

        # Списываем ставку
        current_balance -= bet

        # Логика рандома
        roll = random.uniform(0, 100)
        win = roll <= chance

        if win:
            win_amount = bet * (100 / chance)
            current_balance += win_amount
        else:
            win_amount = 0

        # Сохраняем новый баланс
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (current_balance, user_id))
        await db.commit()

        return {
            "win": win,
            "roll": round(roll, 2),
            "win_amount": round(win_amount, 2),
            "new_balance": round(current_balance, 2)
        }

# --- TELEGRAM BOT ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Открыть FrankGrader", 
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])
    await message.answer(
        "Добро пожаловать в FrankGrader! 🎁\nНажми кнопку ниже, чтобы открыть приложение.",
        reply_markup=keyboard
    )

async def start_bot():
    print("Бот запущен...")
    await dp.start_polling(bot)

async def start_server():
    port = int(os.environ.get("PORT", 8000))
    print(f"Сервер запущен на порту {port}")
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(start_bot(), start_server())

if __name__ == "__main__":
    asyncio.run(main())
