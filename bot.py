import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, ADMIN_ID, WEBAPP_URL
from database import (
    init_db, ensure_user, get_balance, change_balance,
    create_topup, get_topup, set_topup_status,
    create_withdraw, get_withdraw, set_withdraw_status
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class TopupForm(StatesGroup):
    waiting_amount = State()

class WithdrawForm(StatesGroup):
    waiting_item = State()
    waiting_screenshot = State()

@dp.message(CommandStart())
async def start(message: Message):
    ensure_user(message.from_user.id, message.from_user.username)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Открыть казино", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="💫 Пополнить (вручную)", callback_data="topup")],
        [InlineKeyboardButton(text="🏆 Запросить вывод NFT", callback_data="withdraw")],
        [InlineKeyboardButton(text="💰 Мой баланс", callback_data="balance")],
    ])
    await message.answer(
        f"Привет! Твой баланс: {get_balance(message.from_user.id)} кредитов.\n\n"
        "Пополнение: отправь подарок на @ВАШ_АККАУНТ, потом нажми «Пополнить».\n"
        "Вывод NFT: выиграл → скрин → заявка → админ выдаёт вручную.",
        reply_markup=kb
    )

@dp.callback_query(F.data == "balance")
async def balance(cb: CallbackQuery):
    await cb.message.answer(f"💰 Баланс: {get_balance(cb.from_user.id)} кредитов")
    await cb.answer()

@dp.callback_query(F.data == "topup")
async def topup_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Сколько кредитов хочешь пополнить? Отправь число (например, 15).")
    await state.set_state(TopupForm.waiting_amount)
    await cb.answer()

@dp.message(TopupForm.waiting_amount)
async def topup_amount(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Нужно положительное число.")
        return
    amount = int(message.text)
    req_id = create_topup(message.from_user.id, amount)
    await state.clear()

    await message.answer(
        f"Заявка #{req_id} создана.\n"
        f"Теперь отправь подарок на @ВАШ_АККАУНТ на {amount} Stars и жди подтверждения."
    )
    await bot.send_message(
        ADMIN_ID,
        f"💰 Новая заявка на пополнение #{req_id}\n"
        f"Пользователь: @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"Сумма: {amount} кредитов\n\n"
        f"Подтвердить: /approve_topup {req_id}\n"
        f"Отклонить: /reject_topup {req_id}"
    )

@dp.message(Command("approve_topup"))
async def approve_topup(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        req_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Формат: /approve_topup <id>")
        return
    req = get_topup(req_id)
    if not req or req[3] != "pending":
        await message.answer("Заявка не найдена или уже обработана.")
        return
    _, user_id, amount, _ = req
    change_balance(user_id, amount)
    set_topup_status(req_id, "approved")
    await message.answer(f"✅ Заявка #{req_id} одобрена, зачислено {amount}.")
    await bot.send_message(user_id, f"✅ Баланс пополнен на {amount} кредитов!")

@dp.message(Command("reject_topup"))
async def reject_topup(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        req_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Формат: /reject_topup <id>")
        return
    req = get_topup(req_id)
    if not req or req[3] != "pending":
        await message.answer("Заявка не найдена или уже обработана.")
        return
    _, user_id, amount, _ = req
    set_topup_status(req_id, "rejected")
    await message.answer(f"❌ Заявка #{req_id} отклонена.")
    await bot.send_message(user_id, "❌ Заявка на пополнение отклонена.")

@dp.callback_query(F.data == "withdraw")
async def withdraw_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Что выиграл? Напиши название предмета (например, NFT Calendar).")
    await state.set_state(WithdrawForm.waiting_item)
    await cb.answer()

@dp.message(WithdrawForm.waiting_item)
async def withdraw_item(message: Message, state: FSMContext):
    await state.update_data(item_name=message.text)
    await message.answer("Теперь отправь скриншот выигрыша (фото).")
    await state.set_state(WithdrawForm.waiting_screenshot)

@dp.message(WithdrawForm.waiting_screenshot, F.photo)
async def withdraw_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    item_name = data["item_name"]
    file_id = message.photo[-1].file_id
    req_id = create_withdraw(message.from_user.id, item_name, file_id)
    await state.clear()

    await message.answer(f"Заявка на вывод #{req_id} создана. Админ рассмотрит вручную.")
    await bot.send_photo(
        ADMIN_ID,
        photo=file_id,
        caption=(
            f"🏆 Заявка на вывод #{req_id}\n"
            f"Пользователь: @{message.from_user.username} (ID: {message.from_user.id})\n"
            f"Предмет: {item_name}\n\n"
            f"Одобрить: /approve_withdraw {req_id}\n"
            f"Отклонить: /reject_withdraw {req_id}"
        )
    )

@dp.message(Command("approve_withdraw"))
async def approve_withdraw(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        req_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Формат: /approve_withdraw <id>")
        return
    req = get_withdraw(req_id)
    if not req or req[4] != "pending":
        await message.answer("Заявка не найдена или уже обработана.")
        return
    _, user_id, item_name, _, _ = req
    set_withdraw_status(req_id, "approved")
    await message.answer(f"✅ Заявка #{req_id} одобрена. Выдай {item_name} вручную.")
    await bot.send_message(user_id, f"✅ Твоя заявка на вывод {item_name} одобрена. Админ выдаст вручную.")

@dp.message(Command("reject_withdraw"))
async def reject_withdraw(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        req_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Формат: /reject_withdraw <id>")
        return
    req = get_withdraw(req_id)
    if not req or req[4] != "pending":
        await message.answer("Заявка не найдена или уже обработана.")
        return
    _, user_id, item_name, _, _ = req
    set_withdraw_status(req_id, "rejected")
    await message.answer(f"❌ Заявка #{req_id} отклонена.")
    await bot.send_message(user_id, f"❌ Заявка на вывод {item_name} отклонена.")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())