from fpdf import FPDF
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telethon.errors import FloodWaitError
from telethon import TelegramClient
import sqlite3
import re
import asyncio
import nest_asyncio
nest_asyncio.apply()

import os
api_id = 12345678
api_hash = "5d9a5e883b169351e5bbf4f782382b7b"

TOKEN = os.getenv("TOKEN")

ADMIN_USERNAME = "aimen_bott"
ADMIN_URL = "https://t.me/aimen_bott"

client = TelegramClient("session", api_id, api_hash)

users = set()

conn = sqlite3.connect("links.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS links(
link TEXT UNIQUE
)
""")
conn.commit()

patterns = [
    r'https://chat\.whatsapp\.com/[A-Za-z0-9]+',
    r'https://t\.me/[A-Za-z0-9_]+',
    r'https://mega\.nz/[^\s]+',
    r'https://www\.mediafire\.com/[^\s]+'
]


keyboard = [
    [InlineKeyboardButton("🔎 استخراج روابط", callback_data="scan")],
    [InlineKeyboardButton("📁 تحميل النتائج", callback_data="result")],
    [InlineKeyboardButton("👑 لوحة الادمن", callback_data="admin_panel")],
    [InlineKeyboardButton("👤 تواصل مع الادمن", url=ADMIN_URL)]
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user.id
    users.add(user)

    await update.message.reply_text(
        "🤖 بوت استخراج الروابط\n\n"
        "يدعم استخراج:\n"
        "WhatsApp\nTelegram\nMega\nMediaFire\n\n"
        "اختر من القائمة",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data == "scan":
        await query.message.reply_text(
            "📥 ارسل روابط القنوات\nيمكنك ارسال عدة روابط مفصولة بمسافة"
        )

    elif query.data == "result":

        cursor.execute("SELECT link FROM links")
        rows = cursor.fetchall()

        with open("links.txt", "w") as f:
            for r in rows:
                f.write(r[0] + "\n")

        await query.message.reply_document(open("links.txt", "rb"))

    elif query.data == "admin_panel":

        user = query.from_user.username

        if user != ADMIN_USERNAME:
            await query.message.reply_text("❌ هذه القائمة للادمن فقط")
            return

        keyboard_admin = [
            [InlineKeyboardButton("📊 الاحصائيات", callback_data="stats")],
            [InlineKeyboardButton("📢 اذاعة", callback_data="broadcast")],
            [InlineKeyboardButton("📁 تحميل قاعدة البيانات", callback_data=">
            [InlineKeyboardButton("🗑 حذف الروابط", callback_data="clear")]
        ]

        await query.message.reply_text(
            "👑 لوحة تحكم الادمن",
            reply_markup=InlineKeyboardMarkup(keyboard_admin)
        )

    elif query.data == "stats":

        cursor.execute("SELECT COUNT(*) FROM links")
        total_links = cursor.fetchone()[0]

        await query.message.reply_text(
            f"📊 احصائيات البوت\n\n"
            f"👥 المستخدمين: {len(users)}\n"
            f"🔗 الروابط: {total_links}"
        )

    elif query.data == "broadcast":

        context.user_data["broadcast"] = True
        await query.message.reply_text("📢 ارسل الرسالة للاذاعة")

    elif query.data == "db":

        await query.message.reply_document(open("links.db", "rb"))

    elif query.data == "clear":

        cursor.execute("DELETE FROM links")
        conn.commit()
        await query.message.reply_text("🗑 تم حذف الروابط")


async def extract(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await client.start()

    links_input = update.message.text.split()

    msg = await update.message.reply_text("🚀 بدء الفحص")

    scanned = 0
    found_links = set()

    for link in links_input:

        try:
            entity = await client.get_entity(link)
        except BaseException:
            continue

        try:
            async for message in client.iter_messages(entity, limit=None):

                scanned += 1

                if message.text:
                    for p in patterns:
                        found = re.findall(p, message.text)

                        for l in found:
                            found_links.add(l)

                if scanned % 1000 == 0:
                    await msg.edit_text(
                        f"🚀 جاري الفحص...\n\n"
                        f"📨 الرسائل المفحوصة: {scanned}\n"
                        f"🔗 الروابط: {len(found_links)}"
                    )

        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)

        except Exception:
            pass

    for l in found_links:
        try:
            cursor.execute("INSERT INTO links VALUES(?)", (l,))
        except BaseException:
            pass

    conn.commit()

    with open("links.txt", "w") as f:
        for l in found_links:
            f.write(l + "\n")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for l in found_links:
        pdf.cell(0, 10, l, ln=True)

    pdf.output("links.pdf")

    await update.message.reply_document(open("links.txt", "rb"))
    await update.message.reply_document(open("links.pdf", "rb"))

    await update.message.reply_text(
        f"✅ انتهى الفحص\n\n"
        f"📨 الرسائل: {scanned}\n"
        f"🔗 الروابط: {len(found_links)}"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("broadcast"):

        text = update.message.text

        for u in users:
            try:
                await context.bot.send_message(u, text)
            except BaseException:
                pass

        context.user_data["broadcast"] = False
        await update.message.reply_text("✅ تم ارسال الاذاعة")


async def main():

    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(button))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, extract))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("BOT STARTED")

    await app.run_polling()


asyncio.run(main())
