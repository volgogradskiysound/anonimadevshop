import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
)
from aiocryptopay import AioCryptoPay, Networks

# ==================== КОНФИГУРАЦИЯ ====================
# ⚠️ ВСТАВЬТЕ СЮДА СВОИ ТОКЕНЫ
BOT_TOKEN = "8315662398:AAFH8cYtNDHW0lwB_vD0UcdS5qDsZh6sK8M"
CRYPTOBOT_TOKEN = "486634:AAKnNL91kV5Cgz2u9FVlqeN3CjDpnTLPT7w" 
ADMINS = [882242942]  # Вставьте ваш цифровой ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# CryptoBot API
crypto = AioCryptoPay(token=CRYPTOBOT_TOKEN, network=Networks.MAIN_NET)

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    # Таблицы
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        balance REAL DEFAULT 0,
        registration_date TEXT,
        is_blocked INTEGER DEFAULT 0
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        media_type TEXT,
        media_file_id TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        content_type TEXT,
        content TEXT,
        media_type TEXT,
        media_file_id TEXT,
        stock INTEGER DEFAULT 0,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        price REAL,
        purchase_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        invoice_id TEXT,
        amount_rub REAL,
        status TEXT,
        created_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS shop_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS media_settings (
        section TEXT PRIMARY KEY,
        media_type TEXT,
        media_file_id TEXT
    )''')
    
    # Настройки по умолчанию (AnonimaDev Style)
    defaults = {
        'about': '💎 <b>AnonimaDev Studio</b>\n\n🚀 <b>Мы создаем цифровое будущее:</b>\n\n🤖 <i>Telegram Боты любой сложности</i>\n🌐 <i>Современные Веб-сайты</i>\n🔧 <i>Автоматизация бизнеса</i>\n\n🏆 <b>Почему мы?</b>\n• Чистый код\n• Поддержка 24/7\n• Гарантия качества',
        'support': '👨‍💻 <b>Центр поддержки AnonimaDev</b>\n\nВозникли вопросы или проблемы с оплатой?\nНапишите нашему менеджеру:\n\n👉 <b>@anonima_support</b>\n\n<i>Мы отвечаем с 10:00 до 22:00 по МСК</i>',
        'welcome': '👋 <b>Добро пожаловать в экосистему AnonimaDev!</b>\n\nЗдесь вы найдете лучшие решения для вашего бизнеса и автоматизации.\n\n👇 <b>Используйте меню ниже для навигации:</b>',
        'requisites': '💳 <b>СБП / Карта</b>\n<code>0000 0000 0000 0000</code>\n(Т-Банк / Сбер)\n\n👤 Получатель: <b>Anonima Dev.</b>',
        'notify_new_users': '1',
        'notify_purchases': '1',
        'notify_balance': '1'
    }
    
    for key, val in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO shop_settings VALUES (?, ?)", (key, val))
    
    conn.commit()
    conn.close()

# ==================== FSM (СОСТОЯНИЯ) ====================
class AdminState(StatesGroup):
    # Категории
    cat_name = State()
    cat_desc = State()
    cat_media = State()
    
    # Товары
    prod_category = State()
    prod_name = State()
    prod_desc = State()
    prod_price = State()
    prod_content_type = State()
    prod_content = State()
    prod_media = State()
    prod_stock = State()
    
    # Баланс
    balance_user = State()
    balance_amount = State()
    
    # Рассылка
    mail_msg = State()
    mail_confirm = State()
    
    # Пользователи
    user_search = State()
    
    # Медиа
    media_upload = State()
    
    # Настройки
    setting_value = State()

class UserState(StatesGroup):
    replenish_amount = State()

# ==================== КЛАВИАТУРЫ ====================
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Товары и Услуги"), KeyboardButton(text="👤 Мой Кабинет")],
            [KeyboardButton(text="ℹ️ О Студии"), KeyboardButton(text="👨‍💻 Поддержка")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Меню AnonimaDev"
    )

def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="➕ Категория"), KeyboardButton(text="➕ Товар")],
            [KeyboardButton(text="💰 Выдать баланс"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🎨 Медиа"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="🔙 Выйти из админки")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Панель Администратора"
    )

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_db():
    return sqlite3.connect('shop.db')

def get_setting(key):
    with get_db() as conn:
        res = conn.execute("SELECT value FROM shop_settings WHERE key = ?", (key,)).fetchone()
        return res[0] if res else "Текст не установлен"

def get_media(section):
    with get_db() as conn:
        res = conn.execute("SELECT media_type, media_file_id FROM media_settings WHERE section = ?", (section,)).fetchone()
        return res if res else (None, None)

async def send_media_message(message: Message, text: str, reply_markup=None, section=None):
    """Универсальная функция отправки сообщения с медиа или без"""
    media_type, media_file_id = get_media(section) if section else (None, None)
    
    try:
        if media_type == 'photo':
            await message.answer_photo(media_file_id, caption=text, reply_markup=reply_markup)
        elif media_type == 'animation':
            await message.answer_animation(media_file_id, caption=text, reply_markup=reply_markup)
        elif media_type == 'video':
            await message.answer_video(media_file_id, caption=text, reply_markup=reply_markup)
        else:
            await message.answer(text, reply_markup=reply_markup)
    except Exception as e:
        # Если медиа удалено или ошибка, шлем текст
        logger.error(f"Error sending media: {e}")
        await message.answer(text, reply_markup=reply_markup)

async def send_media_to_user(user_id: int, text: str, section=None):
    """Отправка сообщения конкретному юзеру (по ID) с медиа"""
    media_type, media_file_id = get_media(section) if section else (None, None)
    
    try:
        if media_type == 'photo':
            await bot.send_photo(user_id, media_file_id, caption=text)
        elif media_type == 'animation':
            await bot.send_animation(user_id, media_file_id, caption=text)
        elif media_type == 'video':
            await bot.send_video(user_id, media_file_id, caption=text)
        else:
            await bot.send_message(user_id, text)
    except Exception as e:
        logger.error(f"Error sending media to user: {e}")
        await bot.send_message(user_id, text)

# ==================== СТАРТ И МЕНЮ ====================
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    with get_db() as conn:
        # Проверка/Добавление юзера
        exists = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO users (user_id, username, full_name, registration_date) VALUES (?, ?, ?, ?)",
                (user_id, message.from_user.username, message.from_user.full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            # Уведомление админам
            if get_setting('notify_new_users') == '1':
                for admin in ADMINS:
                    try:
                        await bot.send_message(
                            admin,
                            f"👤 <b>Новый клиент!</b>\n"
                            f"ID: <code>{user_id}</code>\n"
                            f"@{message.from_user.username}"
                        )
                    except: pass

        # Проверка бана
        is_blocked = conn.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
        if is_blocked:
            await message.answer("🚫 <b>Доступ к магазину ограничен администратором.</b>")
            return

    welcome_text = get_setting('welcome')
    await send_media_message(message, welcome_text, main_keyboard(), 'welcome')

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS:
        return
    await message.answer("🔓 <b>Добро пожаловать в Панель Управления!</b>", reply_markup=admin_keyboard())

@router.message(F.text == "🔙 Выйти из админки")
async def admin_exit(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear()
    await message.answer("👋 Вы вернулись в главное меню.", reply_markup=main_keyboard())

@router.message(F.text == "❌ Отмена")
async def global_cancel(message: Message, state: FSMContext):
    await state.clear()
    kb = admin_keyboard() if message.from_user.id in ADMINS else main_keyboard()
    await message.answer("❌ Действие отменено.", reply_markup=kb)

# ==================== ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ ====================

@router.message(F.text == "🛍 Товары и Услуги")
async def user_catalog(message: Message):
    with get_db() as conn:
        cats = conn.execute("SELECT id, name FROM categories").fetchall()
    
    if not cats:
        await message.answer("😔 <b>Категории пока не созданы.</b>\nЗагляните позже!")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📂 {c[1]}", callback_data=f"cat_{c[0]}")] for c in cats
    ])
    
    await send_media_message(
        message, 
        "🛍 <b>Каталог товаров и услуг</b>\n\nВыберите категорию:", 
        kb, 
        'catalog'
    )

@router.callback_query(F.data.startswith('cat_'))
async def user_show_products(call: CallbackQuery):
    cat_id = call.data.split('_')[1]
    with get_db() as conn:
        prods = conn.execute("SELECT id, name, price FROM products WHERE category_id = ?", (cat_id,)).fetchall()
        # Получаем инфо о категории, включая медиа
        cat = conn.execute("SELECT name, description, media_type, media_file_id FROM categories WHERE id = ?", (cat_id,)).fetchone()
    
    if not prods:
        await call.answer("В этой категории пока пусто 😔", show_alert=True)
        return
    
    kb = []
    for p in prods:
        kb.append([InlineKeyboardButton(text=f"{p[1]} — {p[2]} RUB", callback_data=f"prod_{p[0]}")])
    kb.append([InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_cats")])
    
    text_header = f"📂 <b>{cat[0]}</b>\n\n{cat[1] if cat[1] else ''}\n\n📦 <b>Выберите товар:</b>"
    
    await call.message.delete()
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    if cat[2] and cat[3]:
        try:
            if cat[2] == 'photo':
                await call.message.answer_photo(cat[3], caption=text_header, reply_markup=markup)
            elif cat[2] == 'video':
                await call.message.answer_video(cat[3], caption=text_header, reply_markup=markup)
            elif cat[2] == 'animation':
                await call.message.answer_animation(cat[3], caption=text_header, reply_markup=markup)
            else:
                 await call.message.answer(text_header, reply_markup=markup)
        except:
             await call.message.answer(text_header, reply_markup=markup)
    else:
        await call.message.answer(text_header, reply_markup=markup)

@router.callback_query(F.data == "back_to_cats")
async def back_to_cats(call: CallbackQuery):
    await call.message.delete()
    await user_catalog(call.message)

@router.callback_query(F.data.startswith('prod_'))
async def user_prod_info(call: CallbackQuery):
    prod_id = call.data.split('_')[1]
    with get_db() as conn:
        prod = conn.execute("SELECT * FROM products WHERE id = ?", (prod_id,)).fetchone()
    
    # prod: id, cat_id, name, desc, price, content_type, content, media_type, media_file_id, stock
    
    text = f"🏷 <b>{prod[2]}</b>\n\n"
    text += f"{prod[3]}\n\n"
    text += f"💵 <b>Цена:</b> <code>{prod[4]} RUB</code>\n"
    text += f"📦 <b>Остаток:</b> {prod[9]} шт."
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Купить за {prod[4]} RUB", callback_data=f"buy_{prod[0]}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"cat_{prod[1]}")]
    ])
    
    if prod[7] and prod[8]: # Если есть медиа
        await call.message.delete()
        try:
            if prod[7] == 'photo':
                await bot.send_photo(call.from_user.id, prod[8], caption=text, reply_markup=kb)
            elif prod[7] == 'video':
                await bot.send_video(call.from_user.id, prod[8], caption=text, reply_markup=kb)
            elif prod[7] == 'animation':
                await bot.send_animation(call.from_user.id, prod[8], caption=text, reply_markup=kb)
        except:
            await bot.send_message(call.from_user.id, text, reply_markup=kb)
    else:
        await call.message.delete()
        await bot.send_message(call.from_user.id, text, reply_markup=kb)

@router.callback_query(F.data.startswith('buy_'))
async def user_buy(call: CallbackQuery):
    prod_id = call.data.split('_')[1]
    user_id = call.from_user.id
    
    with get_db() as conn:
        user = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        prod = conn.execute("SELECT * FROM products WHERE id = ?", (prod_id,)).fetchone()
        
        if prod[9] <= 0:
            await call.answer("🚫 Товар закончился!", show_alert=True)
            return
            
        if user[0] < prod[4]:
            await call.answer(f"❌ Не хватает средств!\nБаланс: {user[0]} RUB\nЦена: {prod[4]} RUB", show_alert=True)
            return
        
        new_bal = user[0] - prod[4]
        conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_bal, user_id))
        conn.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (prod_id,))
        conn.execute("INSERT INTO purchases (user_id, product_id, price, purchase_date) VALUES (?,?,?,?)",
                    (user_id, prod_id, prod[4], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    
    success_msg = f"✅ <b>Покупка успешна!</b>\n\nСписано: {prod[4]} RUB\nОстаток: {new_bal} RUB\n\n👇 <b>Ваш товар:</b>"
    
    if prod[5] == 'text':
        await call.message.answer(f"{success_msg}\n\n<code>{prod[6]}</code>")
    else:
        await call.message.answer(success_msg)
        await call.message.answer_document(prod[6])
        
    if get_setting('notify_purchases') == '1':
        for admin in ADMINS:
            try: await bot.send_message(admin, f"💰 <b>Новая продажа!</b>\nТовар: {prod[2]}\nСумма: {prod[4]} RUB\nПокупатель: {user_id}")
            except: pass

@router.message(F.text == "👤 Мой Кабинет")
async def user_profile(message: Message):
    user_id = message.from_user.id
    with get_db() as conn:
        u = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        purchases = conn.execute("SELECT COUNT(*) FROM purchases WHERE user_id = ?", (user_id,)).fetchone()[0]
    
    txt = f"👤 <b>Личный Кабинет</b>\n\n" \
          f"🆔 ID: <code>{u[0]}</code>\n" \
          f"💳 Баланс: <b>{u[3]} RUB</b>\n" \
          f"📅 В боте с: {u[4]}\n" \
          f"🛍 Куплено товаров: <b>{purchases} шт.</b>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="add_money")]])
    await send_media_message(message, txt, kb, 'profile')

@router.message(F.text == "ℹ️ О Студии")
async def user_about(message: Message):
    text = get_setting('about')
    await send_media_message(message, text, None, 'about')

@router.message(F.text == "👨‍💻 Поддержка")
async def user_support(message: Message):
    text = get_setting('support')
    await send_media_message(message, text, None, 'support')

# ==================== ПОПОЛНЕНИЕ БАЛАНСА ====================
@router.callback_query(F.data == "add_money")
async def pay_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserState.replenish_amount)
    await send_media_message(call.message, "💸 <b>Введите сумму пополнения в РУБЛЯХ:</b>", cancel_kb(), 'replenish')

@router.message(UserState.replenish_amount)
async def pay_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount < 10: raise ValueError
        await state.update_data(amount=amount)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 CryptoBot (USDT/TON)", callback_data="pay_crypto")],
            [InlineKeyboardButton(text="💳 Карта РФ / СБП", callback_data="pay_manual")]
        ])
        await message.answer(f"💰 К оплате: <b>{amount} RUB</b>\nВыберите способ:", reply_markup=kb)
    except:
        await message.answer("❌ Введите корректное число (минимум 10)")

@router.callback_query(F.data == "pay_crypto")
async def pay_crypto(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount_rub = data['amount']
    amount_usdt = round(amount_rub / 98, 2) 
    
    try:
        invoice = await crypto.create_invoice(asset='USDT', amount=amount_usdt)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Оплатить", url=invoice.bot_invoice_url)],
            [InlineKeyboardButton(text="🔄 Проверить", callback_data=f"check_{invoice.invoice_id}")]
        ])
        
        with get_db() as conn:
            conn.execute("INSERT INTO payments (user_id, invoice_id, amount_rub, status, created_date) VALUES (?,?,?,?,?)",
                        (call.from_user.id, invoice.invoice_id, amount_rub, 'pending', datetime.now()))
            conn.commit()
            
        await call.message.edit_text(f"💎 <b>Оплата CryptoBot</b>\n\nСумма: <b>{amount_usdt} USDT</b>\n(По курсу ~98 RUB)\n\nНажмите кнопку после оплаты:", reply_markup=kb)
        await state.clear()
    except Exception as e:
        await call.message.answer("❌ Ошибка CryptoBot API")
        logger.error(e)

@router.callback_query(F.data == "pay_manual")
async def pay_manual(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    req = get_setting('requisites')
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="manual_confirm")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="add_money")]
    ])
    await call.message.edit_text(f"💳 <b>Прямой перевод</b>\n\nСумма: <b>{data['amount']} RUB</b>\n\n📍 <b>Реквизиты:</b>\n{req}", reply_markup=kb)

@router.callback_query(F.data == "manual_confirm")
async def manual_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = call.from_user
    
    for admin in ADMINS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"ap_{user.id}_{data['amount']}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"dp_{user.id}")]
        ])
        try: await bot.send_message(admin, f"💸 <b>Заявка на пополнение</b>\nUser: @{user.username} (ID: {user.id})\nСумма: {data['amount']} RUB", reply_markup=kb)
        except: pass
    
    await call.message.edit_text("⏳ <b>Заявка отправлена администратору!</b>\nОжидайте зачисления.")
    await state.clear()

@router.callback_query(F.data.startswith('check_'))
async def check_crypto(call: CallbackQuery):
    inv_id = int(call.data.split('_')[1])
    invs = await crypto.get_invoices(invoice_ids=[inv_id])
    if invs and invs[0].status == 'paid':
        with get_db() as conn:
            pay = conn.execute("SELECT status, amount_rub FROM payments WHERE invoice_id=?", (inv_id,)).fetchone()
            if pay[0] == 'pending':
                conn.execute("UPDATE payments SET status='paid' WHERE invoice_id=?", (inv_id,))
                conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (pay[1], call.from_user.id))
                conn.commit()
                
                await call.message.delete()
                await send_media_to_user(call.from_user.id, "✅ <b>Оплата прошла! Баланс пополнен.</b>", 'replenish_success')
                return
    await call.answer("⏳ Оплата пока не найдена", show_alert=True)

@router.callback_query(F.data.startswith('ap_'))
async def admin_pay_ok(call: CallbackQuery):
    _, uid, amt = call.data.split('_')
    uid = int(uid)
    with get_db() as conn:
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (float(amt), uid))
        conn.commit()
    
    await send_media_to_user(uid, f"✅ <b>Ваш баланс пополнен на {amt} RUB!</b>", 'replenish_success')
    await call.message.edit_text(f"✅ Одобрено ({amt} RUB)")

@router.callback_query(F.data.startswith('dp_'))
async def admin_pay_no(call: CallbackQuery):
    uid = call.data.split('_')[1]
    await bot.send_message(uid, "❌ <b>Ваш платеж отклонен администратором.</b>")
    await call.message.edit_text("❌ Отклонено")

# ==================== АДМИНКА (ЛОГИКА) ====================

# 1. СТАТИСТИКА
@router.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    if message.from_user.id not in ADMINS: return
    with get_db() as conn:
        uc = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        pc = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        rev = conn.execute("SELECT SUM(price) FROM purchases").fetchone()[0] or 0
    await message.answer(f"📊 <b>Статистика AnonimaDev</b>\n\n👤 Людей: {uc}\n🛒 Покупок: {pc}\n💰 Выручка: <b>{rev} RUB</b>")

# 2. КАТЕГОРИИ
@router.message(F.text == "➕ Категория")
async def adm_add_cat(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.set_state(AdminState.cat_name)
    await message.answer("📝 Введите название категории:", reply_markup=cancel_kb())

@router.message(AdminState.cat_name)
async def adm_cat_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminState.cat_desc)
    await message.answer("📝 Введите описание категории:")

@router.message(AdminState.cat_desc)
async def adm_cat_desc_ask_media(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await state.set_state(AdminState.cat_media)
    await message.answer("📸 Пришлите фото/видео для обложки категории (или напишите 'нет'):")

@router.message(AdminState.cat_media)
async def adm_cat_save(message: Message, state: FSMContext):
    m_type, m_id = None, None
    if message.photo:
        m_type, m_id = 'photo', message.photo[-1].file_id
    elif message.video:
        m_type, m_id = 'video', message.video.file_id
    elif message.animation:
        m_type, m_id = 'animation', message.animation.file_id
        
    data = await state.get_data()
    with get_db() as conn:
        conn.execute("INSERT INTO categories (name, description, media_type, media_file_id) VALUES (?, ?, ?, ?)", 
                     (data['name'], data['desc'], m_type, m_id))
        conn.commit()
    await state.clear()
    await message.answer("✅ Категория добавлена!", reply_markup=admin_keyboard())

# 3. ТОВАРЫ
@router.message(F.text == "➕ Товар")
async def adm_add_prod(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    with get_db() as conn:
        cats = conn.execute("SELECT id, name FROM categories").fetchall()
    if not cats:
        await message.answer("⚠️ Сначала создайте категорию!")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c[1], callback_data=f"selcat_{c[0]}")] for c in cats])
    await message.answer("📂 Выберите категорию:", reply_markup=kb)

@router.callback_query(F.data.startswith('selcat_'))
async def adm_sel_cat(call: CallbackQuery, state: FSMContext):
    await state.update_data(cat_id=call.data.split('_')[1])
    await state.set_state(AdminState.prod_name)
    await call.message.edit_text("📝 Название товара:")

@router.message(AdminState.prod_name)
async def adm_prod_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminState.prod_desc)
    await message.answer("📝 Описание товара:")

@router.message(AdminState.prod_desc)
async def adm_prod_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await state.set_state(AdminState.prod_price)
    await message.answer("💰 Цена (число, RUB):")

@router.message(AdminState.prod_price)
async def adm_prod_price(message: Message, state: FSMContext):
    try:
        pr = float(message.text)
        await state.update_data(price=pr)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 Текст/Ссылка", callback_data="type_text")],
            [InlineKeyboardButton(text="📁 Файл", callback_data="type_file")]
        ])
        await state.set_state(AdminState.prod_content_type)
        await message.answer("📦 Что продаем?", reply_markup=kb)
    except: await message.answer("❌ Введите число!")

@router.callback_query(F.data.startswith('type_'))
async def adm_prod_type(call: CallbackQuery, state: FSMContext):
    t = call.data.split('_')[1]
    await state.update_data(ctype=t)
    await state.set_state(AdminState.prod_content)
    await call.message.edit_text("📥 Отправьте товар (Текст или Файл):")

@router.message(AdminState.prod_content)
async def adm_prod_cont(message: Message, state: FSMContext):
    data = await state.get_data()
    content = message.text if data['ctype'] == 'text' else (message.document.file_id if message.document else None)
    if not content:
        await message.answer("❌ Ошибка. Нужен текст или файл.")
        return
    await state.update_data(content=content)
    await state.set_state(AdminState.prod_media)
    await message.answer("📸 Пришлите фото/видео для обложки (или напишите 'нет'):")

@router.message(AdminState.prod_media)
async def adm_prod_media(message: Message, state: FSMContext):
    m_type, m_id = None, None
    if message.photo:
        m_type, m_id = 'photo', message.photo[-1].file_id
    elif message.video:
        m_type, m_id = 'video', message.video.file_id
    elif message.animation:
        m_type, m_id = 'animation', message.animation.file_id
    
    await state.update_data(m_type=m_type, m_id=m_id)
    await state.set_state(AdminState.prod_stock)
    await message.answer("🔢 Количество товара (шт):")

@router.message(AdminState.prod_stock)
async def adm_prod_stock(message: Message, state: FSMContext):
    try:
        stk = int(message.text)
        d = await state.get_data()
        with get_db() as conn:
            conn.execute(
                "INSERT INTO products (category_id, name, description, price, content_type, content, media_type, media_file_id, stock) VALUES (?,?,?,?,?,?,?,?,?)",
                (d['cat_id'], d['name'], d['desc'], d['price'], d['ctype'], d['content'], d.get('m_type'), d.get('m_id'), stk)
            )
            conn.commit()
        await state.clear()
        await message.answer("✅ Товар создан!", reply_markup=admin_keyboard())
    except: await message.answer("❌ Введите целое число!")

# 4. ПОЛЬЗОВАТЕЛИ
@router.message(F.text == "👥 Пользователи")
async def adm_users(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.set_state(AdminState.user_search)
    await message.answer("🔎 Введите ID или @username пользователя:", reply_markup=cancel_kb())

@router.message(AdminState.user_search)
async def adm_user_find(message: Message, state: FSMContext):
    q = message.text.strip().replace('@', '')
    with get_db() as conn:
        if q.isdigit():
            u = conn.execute("SELECT * FROM users WHERE user_id = ?", (int(q),)).fetchone()
        else:
            u = conn.execute("SELECT * FROM users WHERE username = ?", (q,)).fetchone()
    
    if not u:
        await message.answer("❌ Пользователь не найден")
        return
    
    txt = f"👤 <b>Инфо:</b>\nID: {u[0]}\nName: {u[2]}\nUser: @{u[1]}\nBal: {u[3]} RUB"
    block_txt = "🚫 Заблокировать" if u[5] == 0 else "✅ Разблокировать"
    act = "block" if u[5] == 0 else "unblock"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=block_txt, callback_data=f"usr_{act}_{u[0]}")],[InlineKeyboardButton(text="💰 Выдать баланс", callback_data=f"usr_bal_{u[0]}") ]])
    await message.answer(txt, reply_markup=kb)
    await state.clear()
    await message.answer("Меню:", reply_markup=admin_keyboard())

@router.callback_query(F.data.startswith('usr_block') | F.data.startswith('usr_unblock'))
async def adm_block(call: CallbackQuery):
    act, uid = call.data.split('_')[1], call.data.split('_')[2]
    val = 1 if act == 'block' else 0
    with get_db() as conn:
        conn.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (val, uid))
        conn.commit()
    await call.answer("Выполнено")
    await call.message.edit_text(f"Статус изменен на: {'Бан' if val else 'Активен'}")

# 5. БАЛАНС
@router.message(F.text == "💰 Выдать баланс")
async def adm_give_bal(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.set_state(AdminState.balance_user)
    await message.answer("👤 Введите ID пользователя:", reply_markup=cancel_kb())

@router.message(AdminState.balance_user)
async def adm_bal_usr(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом")
        return
    await state.update_data(uid=message.text)
    await state.set_state(AdminState.balance_amount)
    await message.answer("💰 Сумма (можно с минусом):")

@router.message(AdminState.balance_amount)
async def adm_bal_final(message: Message, state: FSMContext):
    try:
        amt = float(message.text)
        d = await state.get_data()
        with get_db() as conn:
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, d['uid']))
            conn.commit()
        
        # УВЕДОМЛЕНИЕ С МЕДИА (От админа)
        await send_media_to_user(d['uid'], f"⚡️ <b>Ваш баланс изменен:</b> {amt:+} RUB", 'admin_replenish')
        
        await message.answer("✅ Успешно", reply_markup=admin_keyboard())
        await state.clear()
    except: await message.answer("Ошибка")

# 6. РАССЫЛКА
@router.message(F.text == "📢 Рассылка")
async def adm_mail(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.set_state(AdminState.mail_msg)
    await message.answer("📝 Отправьте сообщение (текст/фото/видео) для рассылки:", reply_markup=cancel_kb())

@router.message(AdminState.mail_msg)
async def adm_mail_ask(message: Message, state: FSMContext):
    # Копируем сообщение
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Отправить", callback_data="mail_go")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="mail_stop")]
    ])
    await message.copy_to(message.chat.id, reply_markup=kb) # Предпросмотр
    await state.set_state(AdminState.mail_confirm)

@router.callback_query(F.data == "mail_go")
async def adm_mail_send(call: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("🚀 Рассылка началась...")
    
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()
    
    good, bad = 0, 0
    for u in users:
        try:
            await bot.copy_message(u[0], d['chat_id'], d['msg_id'])
            good += 1
            await asyncio.sleep(0.05) # Антиспам
        except: bad += 1
    
    await call.message.answer(f"🏁 <b>Рассылка завершена!</b>\n✅ Дошло: {good}\n❌ Блок: {bad}", reply_markup=admin_keyboard())
    await state.clear()

@router.callback_query(F.data == "mail_stop")
async def adm_mail_stop(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Отменено", reply_markup=admin_keyboard())

# 7. МЕДИА
@router.message(F.text == "🎨 Медиа")
async def adm_media_menu(message: Message):
    if message.from_user.id not in ADMINS: return
    
    # Клавиатура
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Приветствие", callback_data="med_welcome")],
        [InlineKeyboardButton(text="🛍 Каталог", callback_data="med_catalog")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="med_profile")],
        [InlineKeyboardButton(text="ℹ️ О нас", callback_data="med_about")],
        [InlineKeyboardButton(text="👨‍💻 Поддержка", callback_data="med_support")],
        [InlineKeyboardButton(text="💰 Пополнение", callback_data="med_replenish")],
        [InlineKeyboardButton(text="✅ Успех пополнения", callback_data="med_replenish_success")],
        # НОВЫЕ КНОПКИ
        [InlineKeyboardButton(text="🎁 Пополнение Админом", callback_data="med_admin_replenish")],
        [InlineKeyboardButton(text="📂 Медиа Категории", callback_data="edit_med_cat")],
        [InlineKeyboardButton(text="📦 Медиа Товара", callback_data="edit_med_prod")],
    ])
    await message.answer("🖼 <b>Управление Медиа</b>\nВыберите раздел:", reply_markup=kb)

# --- ЛОГИКА МЕДИА КАТЕГОРИЙ И ТОВАРОВ ---

# Выбор категории для редактирования медиа
@router.callback_query(F.data == "edit_med_cat")
async def adm_med_cat_list(call: CallbackQuery):
    with get_db() as conn:
        cats = conn.execute("SELECT id, name FROM categories").fetchall()
    if not cats:
        await call.answer("Нет категорий")
        return
    kb = []
    for c in cats:
        kb.append([InlineKeyboardButton(text=c[1], callback_data=f"set_med_cat_{c[0]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_media")])
    await call.message.edit_text("📂 Выберите категорию для смены обложки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# Выбор категории для редактирования медиа товара
@router.callback_query(F.data == "edit_med_prod")
async def adm_med_prod_cat_list(call: CallbackQuery):
    with get_db() as conn:
        cats = conn.execute("SELECT id, name FROM categories").fetchall()
    if not cats:
        await call.answer("Нет категорий")
        return
    kb = []
    for c in cats:
        kb.append([InlineKeyboardButton(text=c[1], callback_data=f"pick_prod_cat_{c[0]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_media")])
    await call.message.edit_text("📂 Выберите категорию товара:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# Выбор товара
@router.callback_query(F.data.startswith("pick_prod_cat_"))
async def adm_med_prod_list(call: CallbackQuery):
    cat_id = call.data.split('_')[3]
    with get_db() as conn:
        prods = conn.execute("SELECT id, name FROM products WHERE category_id = ?", (cat_id,)).fetchall()
    if not prods:
        await call.answer("В категории нет товаров", show_alert=True)
        return
    kb = []
    for p in prods:
        kb.append([InlineKeyboardButton(text=p[1], callback_data=f"set_med_prod_{p[0]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="edit_med_prod")])
    await call.message.edit_text("📦 Выберите товар для смены медиа:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# Установка медиа для категории
@router.callback_query(F.data.startswith("set_med_cat_"))
async def adm_ask_med_cat(call: CallbackQuery, state: FSMContext):
    cat_id = call.data.split('_')[3]
    await state.update_data(target='category', target_id=cat_id)
    await state.set_state(AdminState.media_upload)
    await call.message.edit_text("📸 Отправьте новое фото/видео/гиф для КАТЕГОРИИ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="back_media")]]))

# Установка медиа для товара
@router.callback_query(F.data.startswith("set_med_prod_"))
async def adm_ask_med_prod(call: CallbackQuery, state: FSMContext):
    prod_id = call.data.split('_')[3]
    await state.update_data(target='product', target_id=prod_id)
    await state.set_state(AdminState.media_upload)
    await call.message.edit_text("📸 Отправьте новое фото/видео/гиф для ТОВАРА:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="back_media")]]))


@router.callback_query(F.data.startswith('med_'))
async def adm_media_sel(call: CallbackQuery, state: FSMContext):
    sect = call.data.split('_')[1]
    # Если это общие настройки (welcome, replenish, etc)
    await state.update_data(target='setting', sect=sect)
    await state.set_state(AdminState.media_upload)
    
    curr = get_media(sect)
    st = "✅ Установлено" if curr[0] else "❌ Нет картинки"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить текущее", callback_data=f"delmed_{sect}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_media")]
    ])
    
    await call.message.edit_text(f"Раздел: <b>{sect.upper()}</b>\nСтатус: {st}\n\n📸 Отправьте новое фото/гиф/видео:", reply_markup=kb)

@router.callback_query(F.data == "back_media")
async def back_media(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await adm_media_menu(call.message)

@router.message(AdminState.media_upload)
async def adm_media_save(message: Message, state: FSMContext):
    m_type, m_id = None, None
    if message.photo: m_type, m_id = 'photo', message.photo[-1].file_id
    elif message.animation: m_type, m_id = 'animation', message.animation.file_id
    elif message.video: m_type, m_id = 'video', message.video.file_id
    
    if not m_type:
        await message.answer("❌ Это не медиа! Попробуйте снова.")
        return
        
    d = await state.get_data()
    target = d.get('target')
    
    with get_db() as conn:
        if target == 'setting':
            conn.execute("INSERT OR REPLACE INTO media_settings (section, media_type, media_file_id) VALUES (?,?,?)",
                        (d['sect'], m_type, m_id))
            msg = "✅ Медиа раздела обновлено!"
            
        elif target == 'category':
            conn.execute("UPDATE categories SET media_type=?, media_file_id=? WHERE id=?", (m_type, m_id, d['target_id']))
            msg = "✅ Обложка категории обновлена!"
            
        elif target == 'product':
            conn.execute("UPDATE products SET media_type=?, media_file_id=? WHERE id=?", (m_type, m_id, d['target_id']))
            msg = "✅ Медиа товара обновлено!"
            
        conn.commit()
    
    await state.clear()
    await message.answer(msg, reply_markup=admin_keyboard())

@router.callback_query(F.data.startswith('delmed_'))
async def adm_del_med(call: CallbackQuery):
    sect = call.data.split('_')[1]
    with get_db() as conn:
        conn.execute("DELETE FROM media_settings WHERE section = ?", (sect,))
        conn.commit()
    await call.answer("Удалено")
    await adm_media_menu(call.message)

# 8. НАСТРОЙКИ
@router.message(F.text == "⚙️ Настройки")
async def adm_settings(message: Message):
    if message.from_user.id not in ADMINS: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Текст: Приветствие", callback_data="set_welcome")],
        [InlineKeyboardButton(text="✏️ Текст: О нас", callback_data="set_about")],
        [InlineKeyboardButton(text="✏️ Текст: Поддержка", callback_data="set_support")],
        [InlineKeyboardButton(text="💳 Реквизиты", callback_data="set_requisites")]
    ])
    await message.answer("⚙️ <b>Настройки текстов и реквизитов</b>", reply_markup=kb)

@router.callback_query(F.data.startswith('set_'))
async def adm_set_edit(call: CallbackQuery, state: FSMContext):
    key = call.data.split('_')[1]
    await state.update_data(key=key)
    await state.set_state(AdminState.setting_value)
    
    curr = get_setting(key)
    await call.message.edit_text(f"📝 Редактирование: <b>{key.upper()}</b>\n\nТекущее:\n{curr}\n\n👇 Введите новый текст (можно HTML):")

@router.message(AdminState.setting_value)
async def adm_set_save(message: Message, state: FSMContext):
    d = await state.get_data()
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES (?,?)", (d['key'], message.text))
        conn.commit()
    await state.clear()
    await message.answer("✅ Сохранено!", reply_markup=admin_keyboard())

# ==================== ЗАПУСК ====================
async def main():
    init_db()
    dp.include_router(router)
    # Удаляем вебхуки, чтобы бот не падал при старте, если они были
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Bot AnonimaDev Started Successfully!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
