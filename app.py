from flask import Flask
from pyrogram import Client
import threading

# اطلاعات Bot
api_id = 123456   # به جای این api_id واقعی خودتان
api_hash = "your_api_hash"
bot_token = "توکن بات شما"

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is running'

def start_bot():
    app_bot = Client(
        "tavoni-bot",
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token
    )

    @app_bot.on_message()
    def handle_messages(client, message):
        message.reply_text("سلام! این پیام از Web Service ارسال شده است.")

    app_bot.run()

if __name__ == '__main__':
    # اجرای بات در یک Thread جدا
    threading.Thread(target=start_bot).start()
    # اجرای Flask
    app.run(host='0.0.0.0', port=5000)
