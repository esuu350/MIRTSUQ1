import os # Make sure this is at the very top of your imports
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ChatMemberHandler, ContextTypes
)
from flask import Flask
from threading import Thread
import os

# ================= FLASK KEEP-ALIVE SERVER =================
server = Flask('')

@server.route('/')
def home():
    return "Mirt Suq Bot is Online and Awake!"

def run():
    # Railway sets a PORT environment variable automatically
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ================= CONFIG =================
# This tells Python: "Look into Railway's Variables for these names "
TOKEN = os.environ.get("TOKEN")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# These stay the same since they aren't "secret "
CHANNEL = "@mirtsuq"
BOT_USERNAME = "mirtsuqbot"
ADMIN_ID = 8122687721 
DB_HOST = "aws-1-eu-central-1.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.slljeiwvoznnbemvbfcs"
DB_PORT = "6543"

# ================= DB HELPERS =================
def safe_execute(query, params=(), fetch=False):
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER,
            password=DB_PASSWORD, port=DB_PORT, sslmode="require",
            cursor_factory=RealDictCursor
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                return cur.rowcount > 0 
    except Exception as e:
        logger.error(f"❌ DB ERROR: {e}")
        return None

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    is_new = safe_execute(
        "INSERT INTO users (user_id, username, first_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", 
        (user.id, user.username, user.first_name)
    )
    
    if is_new:
        admin_text = f"🆕 **New Registration**\n\n👤 Name: {user.first_name}\n🆔 ID: `{user.id}`\n🔗 User: @{user.username if user.username else 'None'}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")

    if context.args:
        ref_id = context.args[0]
        if ref_id.isdigit() and int(ref_id) != user.id:
            safe_execute("INSERT INTO referrals (referrer_id, invited_user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", 
                         (int(ref_id), user.id))

    welcome_text = (
        f"👋 ሰላም {user.first_name}!\n\n"
        f"ወደ **ምርጥ ሱቅ (Mirt Suq)** የሽልማት ቦት እንኳን መጡ፡፡\n\n"
        f"ውድድሩን ለመቀጠል መጀመሪያ ቻናላችንን ይቀላቀሉ በመቀጠል 'Check Join' የሚለውን ይጫኑ፡፡"
    )
    
    keyboard = [
        [InlineKeyboardButton("📢 ቻናሉን ተቀላቀል", url=f"https://t.me/{CHANNEL.replace('@','')}")],
        [InlineKeyboardButton("✅ ተቀላቅያለሁ / Check Join", callback_data="check_status")],
        [InlineKeyboardButton("📜 ደንብና ሽልማት / Rules", callback_data="rules")]
    ]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    flash_text = (
        "📜 የውድድሩ ደንቦችና ሽልማቶች\n\n"
        "🎁 1ኛ አሸናፊ: K9 Wireless Mic 🎙 (በእጣ)\n"
        "💵 2ኛ አሸናፊ: 500 ብር የጥሬ ገንዘብ (Min. 50 Referrals)\n\n"
        "⚠️ ውጤት የሚገለጸው ቻናሉ 2500 አባላት ሲሞላ ይሆናል!"
    )
    await query.answer(text=flash_text, show_alert=True)

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    
    try:
        member = await context.bot.get_chat_member(CHANNEL, user.id)
        if member.status in ["member", "administrator", "creator"]:
            safe_execute("UPDATE referrals SET verified=TRUE WHERE invited_user_id=%s", (user.id,))
            
            res = safe_execute("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id=%s AND verified=TRUE", (user.id,), fetch=True)
            count = res[0]['cnt'] if res else 0
            
            link = f"https://t.me/{BOT_USERNAME}?start={user.id}"
            dashboard = (
                f"🎫 **የሎተሪ መለያ (ID):** `{user.id}`\n"
                f"👥 **የጋበዙት ሰው:** `{count}`\n"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="check_status")],
                [InlineKeyboardButton("📤 Invite Friends", url=f"https://t.me/share/url?url={link}&text=የምርጥ ሱቅን ቴሌግራም ቻናል በመቀላቀል ብቻ ተሸላሚ ይሁኑ")],
                [InlineKeyboardButton("📜 Rules", callback_data="rules")]
            ]
            
            if user.id == ADMIN_ID:
                keyboard.append([InlineKeyboardButton("🛠 Admin: Top 10", callback_data="leaderboard")])

            try:
                await query.edit_message_text(dashboard, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            except:
                await query.answer()
        else:
            await query.answer("❌ እባክዎ መጀመሪያ ቻናሉን ይቀላቀሉ!", show_alert=True)
    except Exception as e:
        logger.error(f"Membership check error: {e}")
        await query.answer("ስህተት ተፈጥሯል፤ እባክዎ ቆይተው ይሞክሩ።", show_alert=True)

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return

    sql = """SELECT u.first_name, u.username, COUNT(r.id) as cnt FROM users u 
             JOIN referrals r ON u.user_id = r.referrer_id 
             WHERE r.verified = TRUE GROUP BY u.user_id, u.first_name, u.username 
             ORDER BY cnt DESC LIMIT 10"""
    leaders = safe_execute(sql, fetch=True)
    
    text = "🏆 **የመሪዎች ሰንጠረዥ (Top 10)**\n\n"
    for i, r in enumerate(leaders or [], 1):
        text += f"{i}. {r['first_name']} (@{r['username'] or 'N/A'}) — `{r['cnt']}`\n"
    
    await query.message.reply_text(text, parse_mode="Markdown")
    await query.answer()

async def track_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result or result.new_chat_member.status not in ["left", "kicked"]:
        return
    
    user_id = result.from_user.id
    safe_execute("UPDATE referrals SET verified=FALSE WHERE invited_user_id=%s", (user_id,))
    
    res = safe_execute("SELECT referrer_id FROM referrals WHERE invited_user_id=%s", (user_id,), fetch=True)
    if res:
        try:
            await context.bot.send_message(res[0]['referrer_id'], "⚠️ የጋበዙት ሰው ቻናሉን ስለለቀቀ 1 ነጥብ ተቀንሷል።")
        except:
            pass

# ================= RUNNER =================
if __name__ == "__main__":
    # 1. Start the Flask server thread first
    print("🌐 Starting Keep-Alive server...")
    keep_alive()

    # 2. Build and start the Telegram Bot
    print("🚀 Mirt Suq Bot is starting...")
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_status, pattern="check_status"))
    app.add_handler(CallbackQueryHandler(rules, pattern="rules"))
    app.add_handler(CallbackQueryHandler(show_leaderboard, pattern="leaderboard"))
    app.add_handler(ChatMemberHandler(track_leave, ChatMemberHandler.CHAT_MEMBER))
    
    # Important: allowed_updates must include CHAT_MEMBER for leave detection
    app.run_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY, Update.CHAT_MEMBER])
