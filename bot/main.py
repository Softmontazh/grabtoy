import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
import os

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bot/leads.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

# --- FSM ---


class LeadForm(StatesGroup):
    name = State()
    phone = State()
    comment = State()

# --- Бот ---
bot = Bot(API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Оставить заявку")]], resize_keyboard=True)
    await message.answer("Здравствуйте! Я бот для заявок на игрушки для автоматов Хватайка. Нажмите 'Оставить заявку' для оформления.", reply_markup=kb)
    await state.clear()

@dp.message(F.text == "Оставить заявку")
async def start_form(message: Message, state: FSMContext):
    await message.answer("Введите ваше имя:")
    await state.set_state(LeadForm.name)

@dp.message(LeadForm.name)
async def form_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ваш телефон:")
    await state.set_state(LeadForm.phone)

@dp.message(LeadForm.phone)
async def form_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Комментарий к заявке (или пропустите):")
    await state.set_state(LeadForm.comment)

@dp.message(LeadForm.comment)
async def form_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = message.text
    name = data.get("name")
    phone = data.get("phone")
    # --- Сохраняем в БД ---
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO leads (name, phone, comment) VALUES (?, ?, ?)", (name, phone, comment))
    conn.commit()
    conn.close()
    # --- Отправляем админу и создателю ---
    text = f"Новая заявка:\nИмя: {name}\nТелефон: {phone}\nКомментарий: {comment}"
    for chat_id in set([ADMIN_CHAT_ID, CREATOR_ID]):
        if not chat_id:
            continue
        try:
            await bot.send_message(chat_id, text)
        except Exception as e:
            print(f"[Ошибка отправки заявки] chat_id={chat_id}: {e}")
    await message.answer("Спасибо! Ваша заявка принята. Мы свяжемся с вами.")
    await state.clear()

@dp.message(Command("list"))
async def cmd_list(message: Message):
    if message.from_user.id not in (ADMIN_CHAT_ID, CREATOR_ID):
        await message.answer("Только владелец или создатель бота могут просматривать заявки.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, phone, comment, created_at FROM leads ORDER BY created_at DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await message.answer("Заявок пока нет.")
        return
    text = "Последние заявки:\n"
    for r in rows:
        text += f"\nИмя: {r[0]}\nТелефон: {r[1]}\nКомментарий: {r[2]}\nВремя: {r[3]}\n---"
    await message.answer(text)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
