from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
import sqlite3

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        message_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS force_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER UNIQUE,
        invite_link TEXT,
        title TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER UNIQUE
    )
    """)

    conn.commit()
    conn.close()

def save_user(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def add_movie(code, message_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO movies (code, message_id)
        VALUES (?, ?)
        ON CONFLICT(code) DO UPDATE SET message_id=excluded.message_id
    """, (code, message_id))
    conn.commit()
    conn.close()

def get_movie(code):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT message_id FROM movies WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_movies():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, message_id FROM movies")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_movie(code):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE code = ?", (code,))
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def add_admin(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_force_channels():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, invite_link, title FROM force_channels")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_force_channel(channel_id, link, title):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO force_channels (channel_id, invite_link, title)
        VALUES (?, ?, ?)
    """, (channel_id, link, title))
    conn.commit()
    conn.close()

def delete_force_channel(channel_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM force_channels WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()

def stats():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM movies")
    movies = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM force_channels")
    channels = cursor.fetchone()[0]
    conn.close()
    return users, movies, channels

init_db()

# ================= BOT =================
TOKEN = "8376532603:AAFlXDlXolSBT9yfNzspTtcUVSkGjhdrqlk"
PRIVATE_CHANNEL_ID = -1003574627850
ADMIN_PASSWORD = "1234"

WAITING_PASSWORD = set()
WAITING_ADD_MOVIE = {}
WAITING_DELETE = set()
WAITING_ADD_CHANNEL = set()

# ---------- KEYBOARDS ----------
def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino qo‘shish", callback_data="add_movie")],
        [InlineKeyboardButton("📋 Kinolar", callback_data="list_movies")],
        [InlineKeyboardButton("❌ Kino o‘chirish", callback_data="delete_movie")],
        [InlineKeyboardButton("📢 Majburiy kanallar", callback_data="force_channels")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ])

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_admin")]
    ])

def force_sub_keyboard():
    buttons = []
    for _, link, _ in get_force_channels():
        buttons.append([InlineKeyboardButton("➕ Obuna bo‘lish", url=link)])
    buttons.append([InlineKeyboardButton("🔄 Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(buttons)

def force_admin_keyboard():
    channels = get_force_channels()
    buttons = []

    for cid, _, title in channels:
        buttons.append([
            InlineKeyboardButton(
                f"❌ {title}",
                callback_data=f"del_force:{cid}"
            )
        ])

    buttons.append([InlineKeyboardButton("➕ Kanal qo‘shish", callback_data="add_force")])
    buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_admin")])

    return InlineKeyboardMarkup(buttons)

# ---------- FORCE SUB CHECK ----------
async def check_subscriptions(user_id, bot):
    for channel_id, _, _ in get_force_channels():
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status in ("left", "kicked"):
                return False
        except:
            return False
    return True

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    if not await check_subscriptions(update.effective_user.id, context.bot):
        await update.message.reply_text(
            "❌ Botdan foydalanish uchun kanallarga obuna bo‘ling:",
            reply_markup=force_sub_keyboard()
        )
        return
    await update.message.reply_text("🎬 Kino kodini yuboring")

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id):
        await update.message.reply_text("🎛 Admin panel:", reply_markup=admin_keyboard())
        return
    WAITING_PASSWORD.add(user_id)
    await update.message.reply_text("🔐 Admin parolni kiriting:")

# ---------- CALLBACK ----------
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "check_sub":
        if await check_subscriptions(user_id, context.bot):
            await query.message.reply_text("✅ Obuna tasdiqlandi. Kino kodini yuboring")
        else:
            await query.message.reply_text("❌ Hali obuna to‘liq emas")

    if query.data == "back_admin":
        await query.message.reply_text("🎛 Admin panel:", reply_markup=admin_keyboard())
        return

    if not is_admin(user_id):
        return

    if query.data == "force_channels":
        channels = get_force_channels()
        await query.message.reply_text(
            f"📢 Majburiy kanallar ({len(channels)} ta):",
            reply_markup=force_admin_keyboard()
        )

    elif query.data.startswith("del_force:"):
        cid = int(query.data.split(":")[1])
        delete_force_channel(cid)
        await query.message.reply_text(
            "🗑 Kanal o‘chirildi",
            reply_markup=force_admin_keyboard()
        )

    elif query.data == "add_force":
        WAITING_ADD_CHANNEL.add(user_id)
        await query.message.reply_text("➕ -100xxx https://t.me/xxxx")

    elif query.data == "stats":
        u, m, c = stats()
        await query.message.reply_text(
            f"📊 STATISTIKA\n\n👤 Userlar: {u}\n🎬 Kinolar: {m}\n📢 Kanallar: {c}",
            reply_markup=back_keyboard()
        )

# ---------- TEXT HANDLER ----------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not await check_subscriptions(user_id, context.bot):
        await update.message.reply_text("❌ Avval obuna bo‘ling:", reply_markup=force_sub_keyboard())
        return

    if user_id in WAITING_PASSWORD:
        if text == ADMIN_PASSWORD:
            add_admin(user_id)
            WAITING_PASSWORD.remove(user_id)
            await update.message.reply_text("🎛 Admin panel:", reply_markup=admin_keyboard())
        else:
            await update.message.reply_text("❌ Noto‘g‘ri parol")
        return

    if user_id in WAITING_ADD_CHANNEL:
        try:
            cid, link = text.split()
            chat = await context.bot.get_chat(int(cid))
            add_force_channel(int(cid), link, chat.title)
            WAITING_ADD_CHANNEL.remove(user_id)
            await update.message.reply_text("✅ Kanal qo‘shildi", reply_markup=admin_keyboard())
        except:
            await update.message.reply_text("❌ Format: -100xxx https://t.me/xxxx")
        return

    movie = get_movie(text)
    if not movie:
        await update.message.reply_text("❌ Bunday kino yo‘q")
        return

    await context.bot.copy_message(
        chat_id=update.effective_chat.id,
        from_chat_id=PRIVATE_CHANNEL_ID,
        message_id=movie[0]
    )

# ================= APP =================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin_cmd))
app.add_handler(CallbackQueryHandler(callbacks))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

print("Bot ishga tushdi...")
app.run_polling()
