import asyncio
import random
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8756762893:AAHAaPb8Fo50pj-gju38kK45tvOJiPtD314" # ОБЯЗАТЕЛЬНО ЗАМЕНИ!
# Ссылка на твой сервер (пока оставь так, если тестируешь локально)
# Для работы в Telegram нужен HTTPS (об этом ниже)
WEBAPP_URL = "https://user-186.nport.link" 

# --- 1. ИНИЦИАЛИЗАЦИЯ FASTAPI (ВЕБ-СЕРВЕР) ---
app = FastAPI()

# Разрешаем запросы с любых доменов (для тестов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Отдаем HTML файл при заходе на корень сайта
@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# API endpoint для обработки апгрейда
@app.post("/api/upgrade")
async def process_upgrade(request: Request):
    data = await request.json()
    chance = data.get("chance", 50)
    bet = data.get("bet", 10)
    
    # Логика рандома (на сервере, чтобы нельзя было подделать)
    roll = random.uniform(0, 100)
    win = roll <= chance
    
    return {
        "win": win,
        "roll": round(roll, 2),
        "message": "Победа" if win else "Проигрыш"
    }

# --- 2. ИНИЦИАЛИЗАЦИЯ БОТА (AIogram) ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем кнопку, которая открывает Mini App
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Открыть FrankGrader", 
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])
    
    await message.answer(
        "Добро пожаловать в FrankGrader!\nНажми кнопку ниже, чтобы открыть приложение.",
        reply_markup=keyboard
    )

# --- 3. ЗАПУСК ВСЕГО ВМЕСТЕ ---
async def start_bot():
    print("Бот запущен...")
    await dp.start_polling(bot)

async def start_server():
    print("Веб-сервер запущен на http://127.0.0.1:8000")
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Запускаем бота и сервер параллельно
    await asyncio.gather(
        start_bot(),
        start_server()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Выключение...")