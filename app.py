# app.py

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import random
import os
import time
import secrets # ماژول امن برای تولید توکن

app = Flask(__name__, static_folder='static')
CORS(app)

# --- تنظیمات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("FATAL: BOT_TOKEN environment variable not set.")
BALE_API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"

# --- فضاهای ذخیره‌سازی موقت در حافظه ---
linking_tokens = {} # برای نگهداری توکن‌های اتصال: {token: national_id}
otp_storage = {}    # برای نگهداری کدهای OTP: {national_id: {code, chat_id, timestamp}}


# --- مسیر اصلی برای نمایش سایت ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


# --- قدم ۱: تولید توکن اتصال برای فرانت‌اند ---
@app.route('/generate-linking-token', methods=['POST'])
def generate_linking_token():
    data = request.get_json()
    national_id = data.get('national_id')

    if not national_id:
        return jsonify({"error": "کد ملی ارسال نشده است."}), 400

    # TODO: چک کردن وجود کد ملی در پایگاه داده اعضای تعاونی

    # تولید یک توکن امن و منحصر به فرد
    token = secrets.token_urlsafe(16)
    linking_tokens[token] = national_id

    print(f"Generated linking token for NID {national_id}: {token}") # برای دیباگ
    
    # ارسال توکن به فرانت‌اند
    return jsonify({"linking_token": token})


# --- قدم ۲: دریافت پیام از بله و مدیریت توکن ---
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return "ok", 200 # پاسخی که بله متوجه شود پیام دریافت شده

    message = data['message']
    chat_id = message['chat']['id']
    text = message.get('text', '')

    # بررسی اینکه آیا پیام حاوی توکن اتصال است
    if text.startswith('/start '):
        token = text.split(' ', 1)[1] # جدا کردن توکن از دستور /start

        # بررسی وجود توکن در فضای ذخیره‌سازی
        if token in linking_tokens:
            national_id = linking_tokens[token]
            
            # تولید کد OTP
            otp_code = random.randint(10000, 99999)

            # ذخیره کد OTP برای این کاربر
            otp_storage[national_id] = {
                "code": str(otp_code),
                "chat_id": chat_id,
                "timestamp": time.time()
            }
            
            # ارسال کد OTP به کاربر در بله
            message_text = f"کد تایید شما برای ورود به سامانه: {otp_code}"
            requests.post(BALE_API_URL, json={"chat_id": chat_id, "text": message_text})
            
            print(f"Sent OTP to NID {national_id} via chat_id {chat_id}") # برای دیباگ

            # حذف توکن استفاده شده برای جلوگیری از استفاده مجدد
            del linking_tokens[token]
        else:
            # اگر توکن نامعتبر بود
            requests.post(BALE_API_URL, json={"chat_id": chat_id, "text": "لینک ورود شما نامعتبر یا منقضی شده است. لطفاً از سایت دوباره اقدام کنید."})
    
    return "ok", 200


# --- قدم ۳: تایید نهایی کد (در آینده تکمیل می‌شود) ---
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    return jsonify({"message": "این بخش هنوز تکمیل نشده است."})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
