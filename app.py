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

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# --- تنظیمات و اتصالات ---
OTP_EXPIRATION_SECONDS = 120
try:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    BALE_API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)
    print("Successfully connected to Supabase.")
except Exception as e:
    print(f"ERROR: Missing environment variables or failed to connect. {e}")

otp_storage = {}
linking_tokens = {}


# --- مسیر اصلی و پروفایل ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/profile.html')
def serve_profile():
    return send_from_directory(app.static_folder, 'profile.html')

# --- مسیر خواندن پروفایل ---
@app.route('/get-user-profile')
def get_user_profile():
    national_id = request.args.get('nid')
    if not national_id:
        return jsonify({"error": "کد ملی ارسال نشده است."}), 400
    try:
        response = supabase.table('member').select("first_name, last_name, nationalcode, phonenumber, address, postal_code").eq('nationalcode', national_id).single().execute()
        if response.data:
            user_data = response.data
            if 'nationalcode' in user_data:
                user_data['national_id'] = user_data.pop('nationalcode')
            if 'phonenumber' in user_data:
                 user_data['phone_number'] = user_data.pop('phonenumber')
            return jsonify(user_data)
        else:
            return jsonify({"error": "کاربری با این کد ملی یافت نشد."}), 404
    except Exception as e:
        error_message = f"Database Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500


# --- مسیر تولید توکن (با اعتبارسنجی جدید) ---
@app.route('/generate-linking-token', methods=['POST'])
def generate_linking_token():
    data = request.get_json()
    national_id = data.get('national_id')
    phone_number = data.get('phone_number') # شماره موبایل را هم دریافت می‌کنیم

    if not all([national_id, phone_number]):
        return jsonify({"error": "کد ملی وارد شده در سامانه ثبت نشده است"}), 400
    
    try:
        # --- اعتبار سنجی جدید - بخش اول: بررسی وجود کد ملی ---
        response = supabase.table('member').select("nationalcode").eq('nationalcode', national_id).execute()
        if not response.data:
            return jsonify({"error": "کد ملی وارد شده در سامانه ثبت نشده است."}), 404

        # --- اعتبار سنجی جدید - بخش دوم: بررسی تکراری نبودن شماره موبایل ---
        # آیا این شماره برای فرد دیگری ثبت شده است؟
        response = supabase.table('member').select("nationalcode").eq('phonenumber', phone_number).neq('nationalcode', national_id).execute()
        if response.data:
            return jsonify({"error": "این شماره موبایل قبلاً برای عضو دیگری ثبت شده است."}), 409 # 409 Conflict

    except Exception as e:
        print(f"Validation DB Error: {e}")
        return jsonify({"error": "خطا در بررسی اطلاعات."}), 500

    # اگر همه بررسی‌ها موفق بود، توکن را تولید و ارسال کن
    token = secrets.token_urlsafe(16)
    linking_tokens[token] = national_id
    return jsonify({"linking_token": token})


# --- بقیه مسیرهای API (بدون تغییر) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    # ... (بدون تغییر) ...
    data = request.get_json()
    if not data or "message" not in data: return "ok", 200
    message = data['message']
    chat_id = message['chat']['id']
    text = message.get('text', '')
    if text.startswith('/start '):
        token = text.split(' ', 1)[1]
        if token in linking_tokens:
            national_id = linking_tokens.pop(token)
            otp_code = random.randint(10000, 99999)
            otp_storage[national_id] = {"code": str(otp_code), "timestamp": time.time()}
            requests.post(BALE_API_URL, json={"chat_id": chat_id, "text": f"کد تایید شما: {otp_code}"})
    return "ok", 200

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    # ... (بدون تغییر) ...
    data = request.get_json()
    national_id, otp_code = data.get('national_id'), data.get('otp_code')
    if not all([national_id, otp_code]): return jsonify({"error": "اطلاعات ناقص است."}), 400
    if national_id not in otp_storage: return jsonify({"error": "فرآیند ورود یافت نشد."}), 404
    stored_otp = otp_storage[national_id]
    if time.time() - stored_otp["timestamp"] > OTP_EXPIRATION_SECONDS:
        del otp_storage[national_id]
        return jsonify({"error": "کد تایید منقضی شده است."}), 410
    if stored_otp["code"] == otp_code:
        del otp_storage[national_id]
        return jsonify({"message": "ورود با موفقیت انجام شد!"})
    else:
        return jsonify({"error": "کد وارد شده صحیح نیست."}), 400


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
