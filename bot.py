import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import logging
import aiosqlite
from fastapi import FastAPI, Request
from datetime import datetime
import subprocess
import re
import sys
import json
import uvicorn
from parser import parse_data
from aiogram.enums import ParseMode
import aiohttp
from datetime import datetime
API_TOKEN = ""

logging.basicConfig(level=logging.INFO)

app = FastAPI()
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

ADMIN_IDS = [540375100, 7028994705]

button_history = KeyboardButton(text="История покупок")
button_profile = KeyboardButton(text="Профиль")
button_add_balance = KeyboardButton(text="Пополнить баланс")
button_return = KeyboardButton(text="Вернуться назад")
button_buy_subcribe = KeyboardButton(text="Оформить подписку")
button_subscribe_7_days = KeyboardButton(text="7 дней - 390₽")
button_subscribe_30_days = KeyboardButton(text="30 дней - 990₽")

keyboard_subscribe = ReplyKeyboardMarkup(
    keyboard=[
        [button_subscribe_7_days],
        [button_subscribe_30_days],
        [button_return]
    ],
    resize_keyboard=True
)
@dp.message(lambda message: message.text == "Оформить подписку")
async def subscribe_handler(message: Message):
    await message.answer(
        "Выберите срок подписки:",
        reply_markup=keyboard_subscribe
    )
@dp.message(lambda message: message.text == "7 дней - 390₽")
async def subscribe_7_days(message: Message):
    user_id = message.from_user.id
    price = 390

    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT balance, subscribe FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

        if user:
            balance, subscribe = user
            if balance >= price:
                new_balance = balance - price
                new_subscribe = 7 * 86400

                await db.execute(
                    "UPDATE users SET balance = ?, subscribe = ? WHERE user_id = ?",
                    (new_balance, new_subscribe, user_id)
                )
                await db.commit()
                await message.answer(f"Подписка на 7 дней успешно оформлена. Ваш новый баланс: {new_balance}₽", reply_markup=keyboard_main)
                await notify_admins_for_sub(user_id, price)
            else:
                await message.answer("У вас недостаточно средств для оформления подписки. Пополните баланс.", reply_markup=keyboard_main)
        else:
            await message.answer("Пользователь не найден.")

@dp.message(lambda message: message.text == "30 дней - 990₽")
async def subscribe_30_days(message: Message):
    user_id = message.from_user.id
    price = 990

    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT balance, subscribe FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

        if user:
            balance, subscribe = user
            if balance >= price:
                new_balance = balance - price
                new_subscribe = 30 * 86400

                await db.execute(
                    "UPDATE users SET balance = ?, subscribe = ? WHERE user_id = ?",
                    (new_balance, new_subscribe, user_id)
                )
                await db.commit()
                await message.answer(f"Подписка на 30 дней успешно оформлена. Ваш новый баланс: {new_balance}₽", reply_markup=keyboard_main)
                await notify_admins_for_sub(user_id, price)
            else:
                await message.answer("У вас недостаточно средств для оформления подписки. Пополните баланс.", reply_markup=keyboard_main)
        else:
            await message.answer("Пользователь не найден.")
keyboard_main = ReplyKeyboardMarkup(
    keyboard=[
        [button_profile], [button_buy_subcribe],
        [button_history]
    ],
    resize_keyboard=True
)

keyboard_main_subscribe = ReplyKeyboardMarkup(
    keyboard=[
        [button_profile], [button_history]
    ],
    resize_keyboard=True
)

keyboard_profile = ReplyKeyboardMarkup(
    keyboard=[
        [button_add_balance],
        [button_return]
    ],
    resize_keyboard=True
)

async def init_db():
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            balance INTEGER DEFAULT 0,
            subscribe INTEGER DEFAULT 0,
            history_balance TEXT DEFAULT '',
            history_purchase TEXT DEFAULT '',
            banned INTEGER DEFAULT 0
        )
        """)
        await db.commit()

async def add_user(user_id, username):
    async with aiosqlite.connect("users.db") as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()

def is_admin(user_id):
    return user_id in ADMIN_IDS
#################################################################################################
async def send_car_info_to_telegram(number_auto, message):
    title_text, content_values, additional_values, full_url = parse_data(number_auto)

    if not title_text or not content_values:
        await message.answer("Не удалось получить данные.")
        return

    if len(additional_values) != len(content_values):
        await message.answer("Ошибка: количество меток и данных не совпадает.")
        return

    car_info = {
        additional_values[i]: content_values[i] for i in range(len(additional_values))
    }

    async with aiosqlite.connect("users.db") as db:
        user_id = message.from_user.id
        async with db.execute("SELECT subscribe FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

        if user:
            subscribe = user[0]
            if subscribe > 0:
                car_info_message = f"📋 Информация о машине: {title_text}\n"
                for key, value in car_info.items():
                    car_info_message += f"├ {key} `{value}`\n"
                await message.answer(car_info_message, parse_mode="MarkdownV2")
                await message.answer(f"🔗 Полная ссылка: {full_url}\n")
            else:
                car_info_message = f"📋 Информация о машине: {title_text}\n"
                for key, value in car_info.items():
                    car_info_message += f"├ {key} `{value}`\n"
                car_info_message += "\n❗ У вас нет подписки. Оформите её для получения дополнительных данных."
                await message.answer(car_info_message, parse_mode="MarkdownV2")
        else:
            await message.answer("Пользователь не найден.")

def determine_type(input_string):
    if re.match(r'^[A-HJ-NPR-Z0-9]{17}$', input_string):
        return True
    elif re.match(r'^[A-Z0-9\-]{6,17}$', input_string):
        return True
    elif re.match(r'^[АВЕКМНОРСТУХ]{1}\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$', input_string):
        return True
    else:
        return False
    
@dp.message(lambda message: determine_type(message.text))
async def process_message(message: Message):
    input_string = message.text
    print(f"Received message: {input_string}")

    try:
        await message.answer(f"Парсинг для {input_string} был успешно запущен.")
        await send_car_info_to_telegram(input_string, message)
    except subprocess.CalledProcessError as e:
        await message.answer(f"Произошла ошибка при запуске парсера: {e}")

@dp.message(Command(commands=["start"]))
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    await add_user(user_id, username)
    await message.answer("Привет! Добро пожаловать.", reply_markup=keyboard_main)

MERCHANT_ID = ""
SECRET_KEY = ""

@dp.message(lambda message: message.text == "Пополнить баланс")
async def add_balance_handler(message: Message):
    await message.answer("Введите сумму для пополнения:")


async def create_payment(user_id: int, amount: float):
    order_id = f"{user_id}_{int(datetime.utcnow().timestamp())}"
    url = "https://nicepay.io/public/api/payment"
    amount_in_cents = int(amount * 100)
    data = {
        "merchant_id": MERCHANT_ID,
        "secret": SECRET_KEY,
        "order_id": order_id,
        "customer": user_id,
        "amount": amount_in_cents,
        "currency": "RUB",
        "description": "Пополнение баланса"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as response:
            if response.status == 200:
                result = await response.json()
                if result.get("status") == "success":
                    payment_data = result.get("data", {})
                    return {
                        "payment_id": payment_data.get("payment_id"),
                        "link": payment_data.get("link"),
                        "order_id": order_id
                    }
                else:
                    raise Exception(f"Ошибка при создании платежа: {result.get('data', {}).get('message', 'Неизвестная ошибка')}")
            else:
                raise Exception(f"Ошибка HTTP: {response.status}")

@dp.message(lambda message: message.text.isdigit())
async def handle_balance_amount(message: Message):
    user_id = message.from_user.id
    amount = float(message.text)

    if amount <= 0:
        await message.answer("Сумма пополнения должна быть больше нуля. Попробуйте снова.")
        return

    async with aiosqlite.connect("users.db") as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

    try:
        payment_result = await create_payment(user_id, amount)
        payment_url = payment_result["link"]
        order_id = payment_result["order_id"]

        await message.answer(f"Для завершения оплаты перейдите по ссылке: {payment_url}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def notify_admins(user_id: int, amount: float):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💰 Платёж успешен!\n"
                f"🧑‍💻 Пользователь ID: {user_id}\n"
                f"💵 Сумма: {amount}₽\n"
                f"🎉 Платёж был успешно обработан."
            )
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")
async def notify_admins_for_sub(user_id: int, amount: float):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💰 Покупка подписки успешна!\n"
                f"🧑‍💻 Пользователь ID: {user_id}\n"
                f"💵 Сумма: {amount}₽\n"
                f"🎉 Покупка была успешно обработана."
            )
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    params = await request.json()
    order_id = params.get("order_id")
    status = params.get("result")
    amount = params.get("amount") / 100 

    async with aiosqlite.connect("users.db") as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE user_id = ? AND EXISTS (SELECT 1 FROM payments WHERE order_id = ?)",
            (order_id, order_id)
        ) as cursor:
            payment = await cursor.fetchone()

        if payment:
            user_id = payment[0]
            if status == "success":
                await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                await db.commit()
                
                await notify_admins(user_id, amount)
                
                return {"status": "success"}
            else:
                return {"status": "error", "message": "Ошибка при оплате"}
        return {"status": "error", "message": "Платёж не найден"}


@dp.message(Command(commands=["admin"]))
async def admin_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав для доступа к админским функциям.")
        return

    await message.answer("Добро пожаловать в админ-панель! Вот доступные команды:\n"
                         "/ban <user_id> - Заблокировать пользователя\n"
                         "/unban <user_id> - Разблокировать пользователя\n"
                         "/add_balance <user_id> <amount> - Добавить баланс\n"
                         "/subtract_balance <user_id> <amount> - Снять баланс\n"
                         "/extend_subscriptions <user_id> <hours> <days> - Установить подписку")


@dp.message(Command(commands=["extend_subscriptions"]))
async def extend_subscriptions_handler(message: Message):
    async with aiosqlite.connect("users.db") as db:
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав для выполнения этой команды.")
            return
        
        try:
            args = message.text.split()[1:]
            if len(args) != 3:
                raise ValueError("Неверное количество аргументов. Используйте: /extend_subscriptions <user_id> <hours> <days>")

            user_id, hours, days = int(args[0]), int(args[1]), int(args[2])
            if hours < 0 or days < 0:
                raise ValueError("Значения времени не могут быть отрицательными.")
            
            extension_time = hours * 3600 + days * 86400
            cursor = await db.execute(
                "UPDATE users SET subscribe = subscribe + ? WHERE user_id = ? AND subscribe >= 0", 
                (extension_time, user_id)
            )
            await db.commit()

            if cursor.rowcount == 0:
                await message.answer("Пользователь с указанным ID не найден или не имеет активной подписки.")
            else:
                await message.answer(f"Подписка для пользователя с ID {user_id} продлена на {hours} часов и {days} дней.")
        
        except ValueError as ve:
            await message.answer(f"Ошибка: {ve}")
        except Exception as e:
            await message.answer(f"Произошла ошибка: {e}")

@dp.message(lambda message: message.text == "Профиль")
async def profile_handler(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT balance, subscribe, banned FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

    if user:
        balance, subscribe, banned = user
        if banned == 1:
            await message.answer("Ваш профиль заблокирован. Обратитесь в поддержку. @user")
            return
        
        current_time = int(datetime.utcnow().timestamp())
        if subscribe > 0:
            days = subscribe // 86400
            hours = (subscribe % 86400) // 3600
            minutes = (subscribe % 3600) // 60
            subscribe_status = f"Активна: {days} дн, {hours} ч, {minutes} мин"
            f"Ваш баланс: {balance}₽\n"
        else:
            subscribe_status = "Нет активной подписки"
        await message.answer(
            f"Ваш баланс: {balance}₽\n"
            f"Подписка: {subscribe_status}\n",
            reply_markup=keyboard_profile
        )
    else:
        await message.answer("Пользователь не найден.")

@dp.message(Command(commands=["ban"]))
async def ban_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    
    try:
        args = message.text.split()[1:]
        if len(args) != 1:
            raise ValueError("Неверное количество аргументов. Используйте: /ban <user_id>")
        
        user_id = int(args[0])
        async with aiosqlite.connect("users.db") as db:
            cursor = await db.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
        
        if cursor.rowcount == 0:
            await message.answer("Пользователь с указанным ID не найден.")
        else:
            await message.answer(f"Пользователь с ID {user_id} заблокирован.")
    except ValueError as ve:
        await message.answer(f"Ошибка: {ve}")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")

@dp.message(Command(commands=["unban"]))
async def unban_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    
    try:
        args = message.text.split()[1:]
        if len(args) != 1:
            raise ValueError("Неверное количество аргументов. Используйте: /unban <user_id>")
        
        user_id = int(args[0])
        async with aiosqlite.connect("users.db") as db:
            cursor = await db.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
        
        if cursor.rowcount == 0:
            await message.answer("Пользователь с указанным ID не найден.")
        else:
            await message.answer(f"Пользователь с ID {user_id} разблокирован.")
    except ValueError as ve:
        await message.answer(f"Ошибка: {ve}")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")

async def update_subscriptions():
    while True:
        async with aiosqlite.connect("users.db") as db:
            await db.execute("""
            UPDATE users
            SET subscribe = subscribe - 1
            WHERE subscribe > 0
            """)
            await db.commit()
        await asyncio.sleep(1)

@dp.message(lambda message: message.text == "Вернуться назад")
async def return_to_main_handler(message: Message):
    user_id = message.from_user.id

    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT subscribe FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

    if user and user[0] > 0:
        keyboard = keyboard_main_subscribe
    else:
        keyboard = keyboard_main

    await message.answer("Вы вернулись в главное меню.", reply_markup=keyboard)

async def main():
    await init_db()
    asyncio.create_task(update_subscriptions())
    asyncio.create_task(run_fastapi())
    await dp.start_polling(bot)

def start_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)

async def run_fastapi():
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, start_fastapi)

if __name__ == "__main__":
    asyncio.run(main())
