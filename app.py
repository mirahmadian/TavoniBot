from flask import Flask, request
import requests
import random

app = Flask(__name__)

BOT_TOKEN = "1004378078:xtkieq2LxVCvzbAwUHjElG7dHosvq8U2twSdS6OW"
API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if "message" not in data:
        return "no message", 200

    chat_id = data['message']['chat']['id']
    code = random.randint(1000, 9999)

    requests.post(API_URL, json={
        "chat_id": chat_id,
        "text": f"کد تایید شما: {code}"
    })

    return "ok", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
