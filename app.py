# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
import requests
import random
import os
import time
import secrets
import sys

load_dotenv()

# --- بررسی امنیتی اولیه ---
required_vars = ["BOT_TOKEN", "SUPABASE_URL", "SUPABASE_KEY"]
missing_vars = [var for var in required_vars if os.environ.get(var) is None]
if missing_vars:
    print(f"FATAL ERROR: The following environment variables are missing: {', '.join(missing_vars)}")
    sys.exit(1)
print("All critical environment variables are set. Proceeding...")

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/*": {"origins": "*"}})

# --- تنظیمات و اتصالات ---
OTP_EXPIRATION_SECONDS = 120
try:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    BALE_API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)
    print("Successfully connected to Supabase.")
except Exception as e:
    print(f"ERROR: Could not connect to services. {e}")
    sys.exit(1)

otp_storage = {}
linking_tokens = {}

# --- مسیرهای اصلی ---
@app.route('/')
def serve_index(): return send_from_directory(app.static_folder, 'index.html')

@app.route('/profile.html')
def serve_profile(): return send_from_directory(app.static_folder, 'profile.html')

@app.route('/dashboard.html')
def serve_dashboard(): return send_from_directory(app.static_folder, 'dashboard.html')

@app.route('/sell_share.html')
def serve_sell_share():
    return send_from_directory(app.static_folder, 'sell_share.html')

@app.route('/view_offers.html')
def serve_view_offers():
    return send_from_directory(app.static_folder, 'view_offers.html')

# --- API Endpoints ---
@app.route('/get-user-profile')
def get_user_profile():
    national_id = request.args.get('nid')
    if not national_id: return jsonify({"error": "کد ملی ارسال نشده است."}), 400
    try:
        response = supabase.table('member').select("first_name, last_name, nationalcode, phonenumber, address, postal_code").eq('nationalcode', national_id).execute()
        if response.data:
            user_data = response.data[0]
            if 'nationalcode' in user_data: user_data['national_id'] = user_data.pop('nationalcode')
            if 'phonenumber' in user_data: user_data['phone_number'] = user_data.pop('phonenumber')
            return jsonify(user_data)
        else: return jsonify({"error": "کاربری با این کد ملی یافت نشد."}), 404
    except Exception as e: return jsonify({"error": f"Database Error: {str(e)}"}), 500

@app.route('/get-member-data')
def get_member_data():
    national_id = request.args.get('nid')
    if not national_id: return jsonify({"error": "کد ملی ارسال نشده است."}), 400
    try:
        response = supabase.table('member').select("first_name, last_name, share_percentage").eq('nationalcode', national_id).execute()
        if response.data:
            return jsonify(response.data[0])
        else:
            return jsonify({"error": "کاربری با این کد ملی یافت نشد."}), 404
    except Exception as e:
        print(f"Dashboard Data Error: {e}")
        return jsonify({"error": "خطا در دریافت اطلاعات."}), 500

@app.route('/start-login', methods=['POST'])
def start_login():
    data = request.get_json(silent=True)
    if not data or not data.get('national_id'):
        return jsonify({"error": "کد ملی الزامی است"}), 400
    
    national_id = data.get('national_id')

    try:
        response = supabase.table('member').select("phonenumber, chat_id, share_percentage").eq('nationalcode', national_id).execute()
        if not response.data:
            return jsonify({"error": "کد ملی وارد شده در سامانه ثبت نشده است."}), 404
        
        user = response.data[0]
        if user.get('share_percentage') is None:
            supabase.table('member').update({"share_percentage": 100}).eq('nationalcode', national_id).execute()

        if user.get('phonenumber') and user.get('chat_id'):
            otp_code = random.randint(10000, 99999)
            otp_storage[national_id] = {"code": str(otp_code), "timestamp": time.time()}
            otp_message = (f"کد ورود شما به سامانه تعاونی:\n`{otp_code}`\n\n_(برای کپی کردن، کد بالا را لمس کنید)_\n\nاین کد تا ۲ دقیقه دیگر معتبر است.\n*لطفاً این کد را در اختیار دیگران قرار ندهید.*")
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": user['chat_id'], "text": otp_message, "parse_mode": "Markdown"})
            return jsonify({"action": "verify_otp"})
        else:
            token = secrets.token_urlsafe(16)
            linking_tokens[token] = national_id
            return jsonify({"action": "register", "linking_token": token})
    except Exception as e:
        print(f"Login Start Error: {e}")
        return jsonify({"error": "خطا در بررسی اطلاعات کاربر."}), 500

@app.route('/update-user-profile', methods=['POST'])
def update_user_profile():
    data = request.get_json(silent=True)
    if not data: return jsonify({"error": "درخواست نامعتبر است."}), 400
    national_id = data.get('national_id')
    postal_code = data.get('postal_code')
    address = data.get('address')
    if not national_id: return jsonify({"error": "کد ملی برای به‌روزرسانی پروفایل الزامی است."}), 400
    try:
        supabase.table('member').update({"postal_code": postal_code, "address": address}).eq('nationalcode', national_id).execute()
        return jsonify({"message": "اطلاعات شما با موفقیت ذخیره شد."})
    except Exception as e:
        print(f"Profile Update Error: {e}")
        return jsonify({"error": "خطا در ذخیره‌سازی اطلاعات."}), 500

@app.route('/api/sale-offers', methods=['POST'])
def create_sale_offer():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "درخواست نامعتبر است."}), 400

    national_id = data.get('national_id')
    percentage = data.get('percentage_to_sell')
    price = data.get('price')

    if not all([national_id, percentage, price]):
        return jsonify({"error": "اطلاعات ارسالی ناقص است."}), 400

    try:
        supabase.table('sale_offers').insert({
            "seller_national_id": national_id,
            "percentage_to_sell": percentage,
            "price": price,
            "status": "active"
        }).execute()
        return jsonify({"message": "پیشنهاد شما با موفقیت ثبت شد."}), 201
    except Exception as e:
        print(f"Create Offer DB Error: {e}")
        return jsonify({"error": "خطا در ثبت پیشنهاد در پایگاه داده."}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data: return "ok", 200
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id: return "ok", 200
    
    if "contact" in message:
        phone_from_bale = message['contact']['phone_number']
        
        if phone_from_bale.startswith('98'): normalized_phone = '+' + phone_from_bale
        elif phone_from_bale.startswith('0'): normalized_phone = '+98' + phone_from_bale[1:]
        else: normalized_phone = phone_from_bale

        session_data = otp_storage.get(str(chat_id))
        if not session_data or "national_id" not in session_data:
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "فرآیند ثبت‌نام شما یافت نشد."})
            return "ok", 200
        national_id = session_data["national_id"]
        try:
            res = supabase.table('member').select("nationalcode").eq('phonenumber', normalized_phone).execute()
            if res.data:
                requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "این شماره موبایل قبلاً برای عضو دیگری ثبت شده است."})
                return "ok", 200
            
            supabase.table('member').update({"phonenumber": normalized_phone, "chat_id": str(chat_id)}).eq('nationalcode', national_id).execute()
            del otp_storage[str(chat_id)]
            
            otp_code = random.randint(10000, 99999)
            otp_storage[national_id] = {"code": str(otp_code), "timestamp": time.time()}
            otp_message = (f"ثبت‌نام شما با موفقیت انجام شد.\n\nکد ورود شما به سامانه تعاونی:\n`{otp_code}`\n\n_(برای کپی کردن، کد بالا را لمس کنید)_\n\nاین کد تا ۲ دقیقه دیگر معتبر است.\n*لطفاً این کد را در اختیار دیگران قرار ندهید.*")
            payload = {"chat_id": chat_id, "text": otp_message, "parse_mode": "Markdown", "reply_markup": {"remove_keyboard": True}}
            requests.post(f"{BALE_API_URL}/sendMessage", json=payload)
        except Exception as e:
            print(f"Webhook Contact Error: {e}")
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "خطایی در فرآیند ثبت‌نام رخ داد."})
    elif "text" in message and message.get("text").startswith('/start '):
        token = message.get("text").split(' ', 1)[1]
        if token in linking_tokens:
            national_id = linking_tokens.pop(token)
            otp_storage[str(chat_id)] = {"national_id": national_id}
            payload = {
                "chat_id": chat_id, "text": "برای تکمیل ثبت‌نام اولیه، لطفاً روی دکمه