import os
import subprocess
import shutil
import tempfile
import requests
import zipfile
import traceback
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
WORK = tempfile.mkdtemp()
KEYSTORE = "keystore.jks"

@app.route("/")
def home():
    return "Sable APK Builder Alive"

@app.route("/build", methods=["POST"])
def build():
    try:
        data = request.json or {}
        apk_url = data.get("apk_url")
        icon_url = data.get("icon_url")
        app_name = data.get("app_name")

        if not apk_url:
            return jsonify({"error": "apk_url required"}), 400

        target_apk = os.path.join(WORK, "target.apk")
        target_dir = os.path.join(WORK, "target_dir")

        # 1. Download Target APK
        res = requests.get(apk_url, stream=True, timeout=60)
        with open(target_apk, 'wb') as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)

        if not zipfile.is_zipfile(target_apk):
            return jsonify({"error": "Invalid APK file"}), 400

        # 2. Decompile APK
        shutil.rmtree(target_dir, ignore_errors=True)
        subprocess.run(f"apktool d -f -o {target_dir} {target_apk}", shell=True, capture_output=True, text=True)

        manifest_path = os.path.join(target_dir, "AndroidManifest.xml")
        if not os.path.exists(manifest_path):
            return jsonify({"error": "APK highly protected/packed. Cannot modify."}), 500

        # 3. Change App Name
        if app_name:
            with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
                t = f.read()
            import re
            t = re.sub(r'android:label="[^"]*"', f'android:label="{app_name}"', t)
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(t)

        # 4. Change Icon
        if icon_url:
            icon_path = os.path.join(WORK, "new_icon.png")
            res = requests.get(icon_url, stream=True, timeout=60)
            with open(icon_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)

            for root, dirs, files in os.walk(os.path.join(target_dir, "res")):
                for d in dirs:
                    if d.startswith("mipmap"):
                        for ext in ['.png', '.webp']:
                            icon_dest = os.path.join(root, d, f"ic_launcher{ext}")
                            if os.path.exists(icon_dest):
                                shutil.copy(icon_path, icon_dest)

        # 5. Build APK
        unsigned = os.path.join(WORK, "unsigned.apk")
        res = subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Build failed: {res.stderr[:150]}"}), 500

        # 6. Sign APK
        aligned = os.path.join(WORK, "aligned.apk")
        signed = os.path.join(WORK, "signed.apk")
        subprocess.run(f"zipalign -f -p 4 {unsigned} {aligned}", shell=True, check=True)
        subprocess.run(f"apksigner sign --min-sdk-version 21 --ks {KEYSTORE} --ks-pass pass:sable123 --key-pass pass:sable123 --out {signed} {aligned}", shell=True, check=True)

        return send_file(signed, as_attachment=True, download_name="Built_App.apk")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
