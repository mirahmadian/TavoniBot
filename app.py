# app.py

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import random
import os
import time
import secrets

app = Flask(__name__, static_folder='static')
CORS(app)

# --- تنظیمات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("FATAL: BOT_TOKEN environment variable not set.")
BALE_API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"
OTP_EXPIRATION_SECONDS = 120  # کدها بعد از ۱۲۰ ثانیه (۲ دقیقه) منقضی می‌شوند

# --- فضاهای ذخیره‌سازی موقت ---
linking_tokens = {}
otp_storage = {}


@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


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
    data = request.get_json()
    if not data or "message" not in data:
        return "ok", 200

    message = data['message']
    chat_id = message['chat']['id']
    text = message.get('text', '')

    if text.startswith('/start '):
        token = text.split(' ', 1)[1]

        if token in linking_tokens:
            national_id = linking_tokens[token]
            otp_code = random.randint(10000, 99999)
            otp_storage[national_id] = {
                "code": str(otp_code),
                "chat_id": chat_id,
                "timestamp": time.time()
            }
            message_text = f"کد تایید شما برای ورود به سامانه: {otp_code}"
            requests.post(BALE_API_URL, json={"chat_id": chat_id, "text": message_text})
            del linking_tokens[token]
        else:
            requests.post(BALE_API_URL, json={"chat_id": chat_id, "text": "لینک ورود شما نامعتبر یا منقضی شده است. لطفاً از سایت دوباره اقدام کنید."})
    
    return "ok", 200


# --- تابع نهایی برای تایید کد OTP ---
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    national_id = data.get('national_id')
    otp_code = data.get('otp_code')

    if not all([national_id, otp_code]):
        return jsonify({"error": "اطلاعات ناقص است."}), 400

    # بررسی وجود کد در حافظه
    if national_id not in otp_storage:
        return jsonify({"error": "فرآیند ورود شما یافت نشد. لطفاً دوباره درخواست کد دهید."}), 404

    # بررسی انقضای زمانی کد
    stored_otp_data = otp_storage[national_id]
    if time.time() - stored_otp_data["timestamp"] > OTP_EXPIRATION_SECONDS:
        del otp_storage[national_id] # حذف کد منقضی شده
        return jsonify({"error": "کد تایید شما منقضی شده است. لطفاً دوباره تلاش کنید."}), 410

    # بررسی صحت کد
    if stored_otp_data["code"] == otp_code:
        # کد صحیح است
        del otp_storage[national_id] # حذف کد استفاده شده برای امنیت
        
        # TODO: در اینجا باید یک توکن دسترسی (JWT) برای کاربر صادر کرده و به فرانت‌اند بفرستید
        # تا کاربر در مراحل بعدی لاگین بماند.
        
        return jsonify({"message": "ورود با موفقیت انجام شد!"})
    else:
        # کد صحیح نیست
        return jsonify({"error": "کد وارد شده صحیح نیست."}), 400


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
