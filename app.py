from flask import Flask, request
import requests
import random
import os # کتابخانه os را برای خواندن متغیرهای محیطی اضافه کنید

app = Flask(__name__)

# ۱. توکن را از متغیرهای محیطی بخوانید
# این کار هم امن تر است و هم حرفه ای تر
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    # بهتر است برای اطمینان بررسی کنید که دیتا وجود دارد
    if not data or "message" not in data:
        return "no message", 200

    chat_id = data['message']['chat']['id']
    
    # برای اینکه ربات فقط به دستور استارت جواب دهد، این شرط را اضافه کنید
    if data['message'].get('text') == '/start':
        code = random.randint(1000, 9999)

        # ارسال پیام به کاربر
        requests.post(API_URL, json={
            "chat_id": chat_id,
            "text": f"کد تایید شما: {code}"
        })

    return "ok", 200

if __name__ == '__main__':
    # ۲. پورت را از متغیر محیطی بخوانید
    # اگر متغیر PORT وجود نداشت (برای اجرای محلی)، از پورت ۵۰۰۰ استفاده کن
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
