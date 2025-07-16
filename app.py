import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = "1004378078:xtkieq2LxVCvzbAwUHjElG7dHosvq8U2twSdS6OW"
API_URL = f"https://api.bale.ai/bot/v1/{BOT_TOKEN}"

def send_message(chat_id, text, keyboard=None):
    url = f"{API_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if keyboard:
        data["keyboard"] = keyboard
    response = requests.post(url, json=data)
    return response.json()

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.json

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            keyboard = {
                "type": "inline_keyboard",
                "inline_keyboard": [
                    [{"text": "دریافت کد تایید", "callback_data": "get_code"}]
                ]
            }
            send_message(chat_id, "سلام! برای دریافت کد تایید روی دکمه زیر کلیک کنید:", keyboard)

        elif text == "get_code" or (update.get("callback_query") and update["callback_query"]["data"] == "get_code"):
            # اینجا باید کد تایید رو بسازیم و ارسال کنیم
            code = "123456"  # نمونه کد ثابت، بعدا باید پویا بشه
            send_message(chat_id, f"کد تایید شما: {code}")

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=5000)
