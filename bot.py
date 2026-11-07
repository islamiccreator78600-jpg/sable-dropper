import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sable dropper ready. APK file bhej, main fud karke wapas dunga.")

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".apk"):
        await update.message.reply_text("Ye APK nahi hai baby. Sahi APK file bhej.")
        return

    # 1. Progress Message
    progress_msg = await update.message.reply_text("⏳ [□□□□□□□□□□] 0%\nFile server ko bheji ja rahi hai...")

    try:
        # 2. Telegram se file link nikaal
        file = await context.bot.get_file(doc.file_id)
        file_url = file.file_path
        
        await progress_msg.edit_text("⏳ [■■■□□□□□□□] 30%\nServer pe download ho raha hai...")

        # 3. Render ko request bhej
        await progress_msg.edit_text("⏳ [■■■■■□□□□□] 50%\nRender server APK fud kar raha hai... (Wait 1-2 mins)")
        
        response = requests.post(RENDER_URL, json={"apk_url": file_url}, timeout=300)

        if response.status_code == 200:
            await progress_msg.edit_text("⏳ [■■■■■■■■□□] 90%\nFudding complete. File send ho rahi hai...")
            
            # 4. APK wapas bhej
            await update.message.reply_document(
                document=response.content,
                filename="Fudded_App.apk",
                caption="✅ [■■■■■■■■■■] 100%\nLe baby, fudded APK ready hai."
            )
            # Purana progress message delete kar de
            await progress_msg.delete()
        else:
            await progress_msg.edit_text("❌ Error! Render server ne APK return nahi ki.")

    except Exception as e:
        await progress_msg.edit_text(f"❌ Error aaya: {str(e)}")

def main():
    # Bot start karo
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_apk))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
