from flask import Flask, request, jsonify, render_template_string
import requests
import random

app = Flask(__name__)

BOT_TOKEN = "1004378078:xtkieq2LxVCvzbAwUHjElG7dHosvq8U2twSdS6OW"
API_URL = f"https://api.bale.ai/bot{BOT_TOKEN}/sendMessage"

@app.route('/')
def home():
    # فرم ساده برای ارسال Chat ID به صورت دستی
    return render_template_string('''
        <h2>ارسال کد تایید به بله</h2>
        <form method="post" action="/send-code-form">
            Chat ID: <input name="chat_id" required>
            <button type="submit">ارسال کد تایید</button>
        </form>
    ''')

@app.route('/send-code', methods=['POST'])
def send_code_api():
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

@app.route('/send-code-form', methods=['POST'])
def send_code_form():
    chat_id = request.form.get("chat_id")

    if not chat_id:
        return "chat_id لازم است", 400

    code = random.randint(1000, 9999)
    message = f"کد تایید شما: {code}"

    response = requests.post(API_URL, json={
        "chat_id": chat_id,
        "text": message
    })

    if response.ok:
        return f"کد تایید {code} برای chat_id {chat_id} ارسال شد."
    else:
        return "ارسال پیامک در بله ناموفق بود.", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
