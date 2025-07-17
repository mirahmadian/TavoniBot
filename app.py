# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
import requests
import random
import os
import time
import secrets

app = Flask(__name__, static_folder='static')
CORS(app)

# --- تنظیمات و اتصالات ---
OTP_EXPIRATION_SECONDS = 120  # 2 دقیقه

try:
    # اتصال به ربات بله
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    BALE_API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"
    
    # اتصال به پایگاه داده Supabase
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)
    print("Successfully connected to Supabase.")
except Exception as e:
    print(f"ERROR: Missing environment variables or failed to connect. {e}")

# --- فضای ذخیره‌سازی موقت برای کدهای OTP ---
# توجه: در نسخه‌های پیشرفته‌تر، این بخش را هم می‌توان به پایگاه داده منتقل کرد.
otp_storage = {}
linking_tokens = {}

# --- مسیر اصلی برای نمایش سایت ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

# --- مسیر خواندن اطلاعات پروفایل از پایگاه داده واقعی ---
@app.route('/get-user-profile')
def get_user_profile():
    national_id = request.args.get('nid')
    if not national_id:
        return jsonify({"error": "کد ملی ارسال نشده است."}), 400

    try:
        # نام ستون در پایگاه داده شما nationalcode است
        response = supabase.table('members').select("first_name, last_name, nationalcode, phonenumber, email, address, postal_code").eq('nationalcode', national_id).single().execute()
        
        # تغییر نام کلیدها برای هماهنگی با فرانت‌اند
        if response.data:
            user_data = response.data
            user_data['national_id'] = user_data.pop('nationalcode') # تغییر نام کلید
            user_data['phone_number'] = user_data.pop('phonenumber') # تغییر نام کلید
            return jsonify(user_data)
        else:
            return jsonify({"error": "کاربری با این کد ملی یافت نشد."}), 404
            
    except Exception as e:
        print(f"Database SELECT Error: {e}")
        return jsonify({"error": "خطا در ارتباط با پایگاه داده."}), 500

# --- بقیه مسیرهای API (بدون تغییر) ---
@app.route('/generate-linking-token', methods=['POST'])
def generate_linking_token():
    data = request.get_json()
    national_id = data.get('national_id')
    if not national_id:
        return jsonify({"error": "کد ملی ارسال نشده است."}), 400
    token = secrets.token_urlsafe(16)
    linking_tokens[token] = national_id
    return jsonify({"linking_token": token})

@app.route('/webhook', methods=['POST'])
def webhook():
    # این تابع بدون تغییر است
    data = request.get_json()
    if not data or "message" not in data: return "ok", 200
    message, chat_id, text = data['message'], message['chat']['id'], message.get('text', '')
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
    # این تابع بدون تغییر است
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
