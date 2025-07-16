# app.py

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import random
import os
import time  # برای ذخیره زمان انقضای کد

app = Flask(__name__, static_folder='static')
CORS(app)  # فعال‌سازی CORS

# --- تنظیمات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("FATAL: BOT_TOKEN environment variable not set.")
BALE_API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"

# --- ذخیره‌سازی موقت کدها ---
# نکته: این یک روش ذخیره‌سازی موقت در حافظه است.
# اگر سرور ری‌استارت شود، این اطلاعات پاک می‌شود.
# در نسخه‌های بعدی می‌توانیم این را به پایگاه داده Supabase منتقل کنیم.
otp_storage = {}


# --- مسیر اصلی برای نمایش سایت ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


# --- مسیر دریافت درخواست کد تایید ---
@app.route('/request-otp', methods=['POST'])
def request_otp():
    data = request.get_json()
    if not data:
        return jsonify({"error": "درخواست نامعتبر است."}), 400

    national_id = data.get('national_id')
    phone_number = data.get('phone_number')
    chat_id = data.get('chat_id')

    if not all([national_id, phone_number, chat_id]):
        return jsonify({"error": "لطفاً تمام فیلدها را پر کنید."}), 400

    # TODO: در اینجا باید چک کنید که آیا کد ملی در لیست اعضای تعاونی شما هست یا خیر.
    # این کار با یک کوئری به پایگاه داده Supabase انجام خواهد شد.

    # تولید کد ۵ رقمی
    otp_code = random.randint(10000, 99999)
    
    # ارسال پیام به کاربر از طریق ربات بله
    message_text = f"کد تایید شما برای ورود به سامانه تعاونی: {otp_code}"
    payload = {"chat_id": chat_id, "text": message_text}
    
    try:
        response = requests.post(BALE_API_URL, json=payload, timeout=10)
        if response.status_code != 200:
            # اگر ارسال پیام در بله با خطا مواجه شد
            print(f"Bale API Error: {response.text}")
            return jsonify({"error": "خطا در ارسال کد تایید. لطفاً شناسه بله خود را چک کنید."}), 500
    except requests.exceptions.RequestException as e:
        # اگر سرور بله در دسترس نبود
        print(f"Network Error: {e}")
        return jsonify({"error": "خطا در ارتباط با سرویس بله."}), 500

    # ذخیره کد تایید و زمان تولید آن
    # کد ملی را به عنوان کلید در نظر می‌گیریم
    otp_storage[national_id] = {
        "code": str(otp_code),  # کد را به صورت رشته ذخیره می‌کنیم
        "chat_id": chat_id,
        "timestamp": time.time() # زمان فعلی را ذخیره می‌کنیم تا بعداً برای انقضا استفاده کنیم
    }

    print(f"Generated OTP {otp_code} for National ID {national_id}") # برای دیباگ در لاگ‌های Render
    
    return jsonify({"message": "کد تایید با موفقیت به حساب بله شما ارسال شد."})


# این تابع را در مرحله بعد تکمیل خواهیم کرد
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    return jsonify({"message": "این بخش هنوز تکمیل نشده است."})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
