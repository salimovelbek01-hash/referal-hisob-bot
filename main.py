import sqlite3
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ChatMemberHandler, ContextTypes

# --- SOZLAMALAR ---
# ⚠️ FAQAT SHU YERDAGI TOKEnni O'CHIRIB, O'ZINGIZNING HAQIQIY TOKENINGIZNI YOZING!
BOT_TOKEN = "8735075009:AAHdzKHl51zgklK9rRQVuY7M7R6obr4fb4A"
GROUP_CHAT_ID = -1003780449769
ADMIN_ID = 7213008456
REQUIRED_CHANNEL = "@surxondaryoquyonlar"
DATABASE_NAME = "contest_bot.db"


# --- RENDER SERVERI ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot 24/7 rejimda muvaffaqiyatli ishlamoqda!")

def run_web_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), WebServerHandler)
    server.serve_forever()


# --- MAJBURIY OBUNANI TEKSHIRISH FUNKSIYASI ---
async def check_subscription(user_id: int, bot) -> bool:
    if user_id == ADMIN_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        print(f"[Log] Obunani tekshirishda xato: {e}")
        return False
    return False

async def send_subscription_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    channel_link = f"https://t.me{REQUIRED_CHANNEL.replace('@', '')}"
    keyboard = [
        [InlineKeyboardButton("📢 Guruhga a'zo bo'lish", url=channel_link)],
        [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "❌ **Botdan foydalanish uchun avval guruhimizga a'zo bo'lishingiz shart!**"
    if is_callback:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS contests (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, status TEXT DEFAULT 'active')")
    cursor.execute("CREATE TABLE IF NOT EXISTS candidates (id INTEGER PRIMARY KEY AUTOINCREMENT, contest_id INTEGER, name TEXT, invite_link TEXT, score INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

init_db()

def get_active_contest_id():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM contests WHERE status = 'active' ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row if row else None


# --- BOT BUYRUQLARI ---
async def create_contest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Bu buyruq faqat admin uchun!")
        return
    if not context.args:
        await update.message.reply_text("❌ Foydalanish: `/new_contest AksiyaNomi`")
        return
    title = " ".join(context.args)
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE contests SET status = 'finished' WHERE status = 'active'")
    cursor.execute("INSERT INTO contests (title, status) VALUES (?, 'active')", (title,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🚀 **Yangi aksiya ochildi:**\n🏆 *{title}*", parse_mode="Markdown")

async def add_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    contest_id = get_active_contest_id()
    if not contest_id:
        await update.message.reply_text("❌ Avval `/new_contest` buyrug'i bilan aksiya yarating.")
        return
    if not context.args:
        await update.message.reply_text("❌ Foydalanish: `/add NomzodIsmi`")
        return
    name = " ".join(context.args)
    try:
        link_obj = await context.bot.create_chat_invite_link(chat_id=GROUP_CHAT_ID, name=f"Contest: {name}")
        invite_link = link_obj.invite_link
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO candidates (contest_id, name, invite_link) VALUES (?, ?, ?)", (contest_id, name, invite_link))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Nomzod qo'shildi: *{name}*\nHavola: `{invite_link}`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await send_subscription_alert(update, context)
        return
    contest_id = get_active_contest_id()
    if not contest_id:
        await update.message.reply_text("🐰 Hozircha hech qanday faol aksiya o'tkazilmayapti.")
        return
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM candidates WHERE contest_id = ?", (contest_id,))
    candidates = cursor.fetchall()
    cursor.execute("SELECT title FROM contests WHERE id = ?", (contest_id,))
    contest_title = cursor.fetchone()
    conn.close()
    if not candidates:
        await update.message.reply_text(f"🏆 **Konkurs:** {contest_title}\n\n🐰 Ishtirokchilar yo'q.")
        return
    keyboard = []
    for cid, name in candidates:
        keyboard.append([InlineKeyboardButton(f"🗳 {name} uchun havola", callback_data=f"vote_{cid}")])
    keyboard.append([InlineKeyboardButton("📊 Jonli Reyting", callback_data="show_rating")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"👋 **{contest_title} botiga xush kelibsiz!**", reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if data == "check_sub":
        is_subscribed = await check_subscription(user_id, context.bot)
        if is_subscribed:
            await query.message.reply_text("🎉 A'zoligingiz tasdiqlandi. Qaytadan `/start` buyrug'ini bosing.")
        else:
            await query.message.reply_text("❌ Siz hali ham guruhga a'zo bo'lmadingiz!")
        return
    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await send_subscription_alert(update, context, is_callback=True)
        return
    if data.startswith("vote_"):
        cid = int(data.split("_")[1])
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, invite_link FROM candidates WHERE id = ?", (cid,))
        res = cursor.fetchone()
        conn.close()
        if res:
            await query.message.reply_text(f"🔗 **{res[0]}** uchun taklif havolasi:\n`{res[1]}`", parse_mode="Markdown")
    elif data == "show_rating":
        contest_id = get_active_contest_id()
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, score FROM candidates WHERE contest_id = ? ORDER BY score DESC", (contest_id,))
        rows = cursor.fetchall()
        conn.close()
        text = "📊 **Jonli Reyting Natijalari:**\n\n"
        for i, (name, score) in enumerate(rows, start=1):
            text += f"{i}. {name} — *{score} ta odam*\n"
        await query.message.reply_text(text, parse_mode="Markdown")

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member = update.chat_member
    if not chat_member: return
    if chat_member.old_chat_member.status in ["left", "kicked"] and chat_member.new_chat_member.status in ["member", "administrator"]:
        invite_link = chat_member.invite_link
        if invite_link:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM candidates WHERE invite_link = ?", (invite_link.invite_link,))
            candidate = cursor.fetchone()
            if candidate:
                cursor.execute("UPDATE candidates SET score = score + 1 WHERE id = ?", (candidate[0],))
                conn.commit()
            conn.close()

async def finish_contest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return
    contest_id = get_active_contest_id()
    if not contest_id: return
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE contests SET status = 'finished' WHERE id = ?", (contest_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("🎉 **Konkurs yakunlandi va faol aksiya yopildi!** Natijalarni reyting tugmasi orqali ko'rishingiz mumkin.")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new_contest", create_contest))
    app.add_handler(CommandHandler("add", add_candidate))
    app.add_handler(CommandHandler("finish", finish_contest))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.CHAT_MEMBER))
    print("Konkurs boti muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
