# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
import requests
import random
import os
import time
import secrets
import sys

load_dotenv()

# --- بررسی امنیتی اولیه (بدون تغییر) ---
required_vars = ["BOT_TOKEN", "SUPABASE_URL", "SUPABASE_KEY"]
missing_vars = [var for var in required_vars if os.environ.get(var) is None]
if missing_vars:
    print(f"FATAL ERROR: The following environment variables are missing: {', '.join(missing_vars)}")
    sys.exit(1)
print("All critical environment variables are set. Proceeding...")

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/*": {"origins": "*"}})

# --- تنظیمات و اتصالات (بدون تغییر) ---
OTP_EXPIRATION_SECONDS = 120
try:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    BALE_API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)
    print("Successfully connected to Supabase.")
except Exception as e:
    print(f"ERROR: Could not connect to services. {e}")
    sys.exit(1)

otp_storage = {}
linking_tokens = {}

# --- مسیرهای اصلی (بدون تغییر) ---
@app.route('/')
def serve_index(): return send_from_directory(app.static_folder, 'index.html')
@app.route('/profile.html')
def serve_profile(): return send_from_directory(app.static_folder, 'profile.html')

# --- API Endpoints ---
@app.route('/get-user-profile')
def get_user_profile():
    # ... (این تابع بدون تغییر باقی می‌ماند) ...
    pass

@app.route('/start-login', methods=['POST'])
def start_login():
    data = request.get_json(silent=True)
    if not data or not data.get('national_id'):
        return jsonify({"error": "کد ملی الزامی است"}), 400
    
    national_id = data.get('national_id')

    try:
        response = supabase.table('member').select("phonenumber, chat_id").eq('nationalcode', national_id).single().execute()
        
        if not response.data:
            return jsonify({"error": "کد ملی وارد شده در سامانه ثبت نشده است."}), 404

        user = response.data
        if user.get('phonenumber') and user.get('chat_id'):
            otp_code = random.randint(10000, 99999)
            otp_storage[national_id] = {"code": str(otp_code), "timestamp": time.time()}
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": user['chat_id'], "text": f"کد تایید شما: {otp_code}"})
            return jsonify({"action": "verify_otp"})
        else:
            token = secrets.token_urlsafe(16)
            linking_tokens[token] = national_id
            return jsonify({"action": "register", "linking_token": token})

    except Exception as e:
        print(f"Login Start Error: {e}")
        return jsonify({"error": "خطا در بررسی اطلاعات کاربر."}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data: return "ok", 200

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id: return "ok", 200
    
    # سناریوی اول: کاربر شماره موبایل خود را به اشتراک گذاشته
    if "contact" in message:
        phone_from_bale = message['contact']['phone_number']
        national_id = otp_storage.get(str(chat_id), {}).get("national_id")

        if not national_id:
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "فرآیند ثبت‌نام شما یافت نشد. لطفاً از سایت دوباره اقدام کنید."})
            return "ok", 200

        try:
            # چک می‌کنیم شماره موبایل برای فرد دیگری ثبت نشده باشد
            res = supabase.table('member').select("nationalcode").eq('phonenumber', phone_from_bale).execute()
            if res.data:
                requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "این شماره موبایل قبلاً در سامانه برای عضو دیگری ثبت شده است."})
                return "ok", 200
            
            # شماره موبایل و chat_id را در دیتابیس ذخیره می‌کنیم
            supabase.table('member').update({"phonenumber": phone_from_bale, "chat_id": chat_id}).eq('nationalcode', national_id).execute()
            
            # حالا OTP را ارسال می‌کنیم
            otp_code = random.randint(10000, 99999)
            otp_storage[national_id] = {"code": str(otp_code), "timestamp": time.time()}
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": chat_id, "text": f"ثبت‌نام شما با موفقیت انجام شد.\nکد تایید شما: {otp_code}"})

        except Exception as e:
            print(f"Webhook Contact Error: {e}")
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "خطایی در فرآیند ثبت‌نام رخ داد. لطفاً با پشتیبانی تماس بگیرید."})

    # سناریوی دوم: کاربر روی لینک هوشمند کلیک کرده
    elif "text" in message and message.get("text").startswith('/start '):
        token = message.get("text").split(' ', 1)[1]
        if token in linking_tokens:
            national_id = linking_tokens.pop(token)
            otp_storage[str(chat_id)] = {"national_id": national_id} # ارتباط موقت بین chat_id و national_id
            
            payload = {
                "chat_id": chat_id,
                "text": "برای تکمیل ثبت‌نام اولیه، لطفاً روی دکمه زیر کلیک کرده و شماره موبایل خود را با ما به اشتراک بگذارید.",
                "reply_markup": {
                    "keyboard": [[{"text": "🔒 اشتراک‌گذاری شماره موبایل", "request_contact": True}]],
                    "resize_keyboard": True, "one_time_keyboard": True
                }
            }
            requests.post(f"{BALE_API_URL}/sendMessage", json=payload)

    return "ok", 200

# تابع verify-otp بدون تغییر باقی می‌ماند
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    # ... (کد این تابع مثل قبل است) ...
    pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)