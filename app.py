from flask import Flask, request, jsonify
import requests
import random

app = Flask(__name__)

BOT_TOKEN = "1004378078:xtkieq2LxVCvzbAwUHjElG7dHosvq8U2twSdS6OW"
API_URL = f"https://api.bale.ai/bot{BOT_TOKEN}/sendMessage"

@app.route('/send-code', methods=['POST'])
def send_code():
    data = request.json
    chat_id = data.get("chat_id")

    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    code = random.randint(1000, 9999)
    message = f"کد تایید شما: {code}"

    response = requests.post(API_URL, json={
        "chat_id": chat_id,
        "text": message
    })

    if response.ok:
        return jsonify({"message": "کد تایید ارسال شد", "code": code})
    else:
        return jsonify({"error": "ارسال پیامک در بله ناموفق بود."}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.json
    print(update)  # لاگ کردن پیام دریافتی
    return jsonify({"ok": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
