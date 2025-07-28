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
def serve_sell_share(): return send_from_directory(app.static_folder, 'sell_share.html')

@app.route('/view_offers.html')
def serve_view_offers(): return send_from_directory(app.static_folder, 'view_offers.html')

@app.route('/offer_detail.html')
def serve_offer_detail(): return send_from_directory(app.static_folder, 'offer_detail.html')

@app.route('/manage_offer.html')
def serve_manage_offer(): return send_from_directory(app.static_folder, 'manage_offer.html')

@app.route('/health-check')
def health_check(): return '', 204

# --- API Endpoints ---
@app.route('/api/member-data')
def get_member_data():
    national_id = request.args.get('nid')
    if not national_id: return jsonify({"error": "کد ملی ارسال نشده است."}), 400
    try:
        member_res = supabase.table('member').select("first_name, last_name, share_percentage, nationalcode, phonenumber, address, postal_code").eq('nationalcode', national_id).execute()
        if not member_res.data:
            return jsonify({"error": "کاربری با این کد ملی یافت نشد."}), 404
        member_data = member_res.data[0]
        offers_res = supabase.table('sale_offers').select('percentage_to_sell').eq('seller_national_id', national_id).eq('status', 'active').execute()
        listed_percentage = sum(offer['percentage_to_sell'] for offer in offers_res.data)
        member_data['available_share_percentage'] = member_data.get('share_percentage', 100) - listed_percentage
        return jsonify(member_data)
    except Exception as e:
        print(f"Dashboard/Profile Data Error: {e}")
        return jsonify({"error": "خطا در دریافت اطلاعات کاربر."}), 500

@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.get_json(silent=True)
    if not data: return jsonify({"error": "درخواست نامعتبر است."}), 400
    if data.get('honeypot') and data.get('honeypot') != '':
        time.sleep(random.uniform(1, 3))
        return jsonify({"action": "register", "linking_token": "fake_token_for_bot"})
    national_id = data.get('national_id')
    if not national_id: return jsonify({"error": "کد ملی الزامی است"}), 400
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
            otp_message = (f"*تعاونی مصرف کارکنان سازمان حج و زیارت*\n\nسهامدار گرامی، کد محرمانه زیر جهت ورود به سامانه تعاونی مصرف می‌باشد.\n*لطفاً این کد را در اختیار دیگران قرار ندهید.*\n\nکد ورود شما: `{otp_code}`")
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": user['chat_id'], "text": otp_message, "parse_mode": "Markdown"})
            return jsonify({"action": "verify_otp"})
        else:
            token = secrets.token_urlsafe(16)
            linking_tokens[token] = national_id
            return jsonify({"action": "register", "linking_token": token})
    except Exception as e:
        print(f"Login Start Error: {e}")
        return jsonify({"error": "خطا در بررسی اطلاعات کاربر."}), 500

@app.route('/api/update-profile', methods=['POST'])
def update_user_profile():
    data = request.get_json(silent=True)
    if not data: return jsonify({"error": "درخواست نامعتبر است."}), 400
    national_id = data.get('national_id')
    postal_code = data.get('postal_code')
    address = data.get('address')
    if not all([national_id, postal_code, address]) or postal_code == '' or address == '':
        return jsonify({"error": "تمام فیلدها الزامی هستند."}), 400
    try:
        supabase.table('member').update({"postal_code": postal_code, "address": address}).eq('nationalcode', national_id).execute()
        return jsonify({"message": "اطلاعات شما با موفقیت ذخیره شد."})
    except Exception as e:
        print(f"Profile Update Error: {e}")
        return jsonify({"error": "خطا در ذخیره‌سازی اطلاعات."}), 500

@app.route('/api/sale-offers', methods=['GET', 'POST'])
def handle_sale_offers():
    if request.method == 'POST':
        data = request.get_json(silent=True)
        if not data: return jsonify({"error": "درخواست نامعتبر است."}), 400
        national_id = data.get('national_id')
        percentage_to_sell = data.get('percentage_to_sell')
        price = data.get('price')
        if not all([national_id, percentage_to_sell, price]):
            return jsonify({"error": "اطلاعات ارسالی ناقص است."}), 400
        try:
            member_res = supabase.table('member').select("share_percentage").eq('nationalcode', national_id).execute()
            if not member_res.data: return jsonify({"error": "کاربر فروشنده یافت نشد."}), 404
            total_shares = member_res.data[0].get('share_percentage', 100)
            offers_res = supabase.table('sale_offers').select('percentage_to_sell').eq('seller_national_id', national_id).eq('status', 'active').execute()
            already_listed_percentage = sum(offer['percentage_to_sell'] for offer in offers_res.data)
            if (already_listed_percentage + percentage_to_sell) > total_shares:
                remaining = total_shares - already_listed_percentage
                return jsonify({"error": f"شما سهم کافی برای فروش ندارید. تنها می‌توانید {remaining}% دیگر از سهم خود را برای فروش بگذارید."}), 400
            supabase.table('sale_offers').insert({ "seller_national_id": national_id, "percentage_to_sell": percentage_to_sell, "price": price, "status": "active" }).execute()
            return jsonify({"message": "پیشنهاد شما با موفقیت ثبت شد."}), 201
        except Exception as e:
            print(f"Create Offer DB Error: {e}")
            return jsonify({"error": "خطا در ثبت پیشنهاد در پایگاه داده."}), 500
    if request.method == 'GET':
        try:
            response = supabase.table('sale_offers').select('*, member:seller_national_id ( first_name, last_name )').eq('status', 'active').execute()
            if response.data:
                offers = []
                for offer in response.data:
                    if offer['percentage_to_sell'] > 0:
                        offer['normalized_price'] = int((offer['price'] / offer['percentage_to_sell']) * 100)
                    else: offer['normalized_price'] = 0
                    offers.append(offer)
                sorted_offers = sorted(offers, key=lambda x: x['normalized_price'])
                return jsonify(sorted_offers)
            else: return jsonify([])
        except Exception as e:
            print(f"Get Offers DB Error: {e}")
            return jsonify({"error": "خطا در دریافت لیست پیشنهادها."}), 500

@app.route('/api/my-offers')
def get_my_offers():
    national_id = request.args.get('nid')
    if not national_id: return jsonify({"error": "کد ملی ارسال نشده است."}), 400
    try:
        response = supabase.rpc('get_offers_with_request_count', {'seller_nid': national_id}).execute()
        if response.data:
            sorted_offers = sorted(response.data, key=lambda x: x['price'], reverse=True)
            return jsonify(sorted_offers)
        else: return jsonify([])
    except Exception as e:
        print(f"Error fetching seller offers: {e}")
        return jsonify({"error": "خطا در دریافت پیشنهادهای شما."}), 500

@app.route('/api/my-offers/<int:offer_id>')
def get_my_offer_with_requests(offer_id):
    national_id = request.args.get('nid')
    if not national_id: return jsonify({"error": "شناسه کاربر نامشخص است."}), 400
    try:
        offer_res = supabase.table('sale_offers').select('*').eq('id', offer_id).eq('seller_national_id', national_id).execute()
        if not offer_res.data:
            return jsonify({"error": "این پیشنهاد متعلق به شما نیست یا یافت نشد."}), 404
        offer_details = offer_res.data[0]
        requests_res = supabase.table('purchase_requests').select('*, member:buyer_national_id (first_name, last_name)').eq('offer_id', offer_id).execute()
        status_map = {'active': 'فعال', 'pending': 'در حال بررسی', 'approved': 'تایید شده', 'rejected': 'رد شده', 'completed': 'تکمیل شده', 'cancelled': 'لغو شده'}
        offer_details['status'] = status_map.get(str(offer_details.get('status', '')).strip(), offer_details.get('status', ''))
        translated_requests = []
        if requests_res.data:
            for req in requests_res.data:
                req_status_en = str(req.get('status', '')).strip()
                req['status'] = status_map.get(req_status_en, req_status_en)
                translated_requests.append(req)
        offer_details['purchase_requests'] = translated_requests
        return jsonify(offer_details)
    except Exception as e:
        print(f"Error fetching offer with requests: {e}")
        return jsonify({"error": "خطا در دریافت اطلاعات مدیریت پیشنهاد."}), 500

@app.route('/api/sale-offers/<int:offer_id>')
def get_offer_details(offer_id):
    try:
        response = supabase.table('sale_offers').select('*, member:seller_national_id ( first_name, last_name )').eq('id', offer_id).execute()
        if response.data:
            offer = response.data[0]
            if offer['percentage_to_sell'] > 0:
                offer['normalized_price'] = int((offer['price'] / offer['percentage_to_sell']) * 100)
            else: offer['normalized_price'] = 0
            return jsonify(offer)
        else:
            return jsonify({"error": "پیشنهاد مورد نظر یافت نشد."}), 404
    except Exception as e:
        print(f"Get Offer Detail Error: {e}")
        return jsonify({"error": "خطا در دریافت اطلاعات پیشنهاد."}), 500
        
@app.route('/api/purchase-requests', methods=['POST'])
def create_purchase_request():
    data = request.get_json(silent=True)
    if not data: return jsonify({"error": "درخواست نامعتبر"}), 400
    offer_id = data.get('offer_id')
    buyer_national_id = data.get('buyer_national_id')
    if not all([offer_id, buyer_national_id]):
        return jsonify({"error": "اطلاعات ارسالی ناقص است."}), 400
    try:
        offer_res = supabase.table('sale_offers').select('seller_national_id').eq('id', offer_id).eq('status', 'active').execute()
        if not offer_res.data:
            return jsonify({"error": "این پیشنهاد دیگر فعال نیست یا وجود ندارد."}), 404
        seller_id = offer_res.data[0]['seller_national_id']
        if seller_id == buyer_national_id:
            return jsonify({"error": "شما نمی‌توانید پیشنهاد خودتان را خریداری کنید."}), 400
        duplicate_check = supabase.table('purchase_requests').select('id').eq('offer_id', offer_id).eq('buyer_national_id', buyer_national_id).execute()
        if duplicate_check.data:
            return jsonify({"error": "شما قبلاً برای این پیشنهاد درخواست خرید ثبت کرده‌اید."}), 409
        supabase.table('purchase_requests').insert({"offer_id": offer_id, "buyer_national_id": buyer_national_id}).execute()
        seller_info_res = supabase.table('member').select('chat_id, first_name, last_name').eq('nationalcode', seller_id).execute()
        buyer_info_res = supabase.table('member').select('first_name, last_name').eq('nationalcode', buyer_national_id).execute()
        if seller_info_res.data and seller_info_res.data[0].get('chat_id') and buyer_info_res.data:
            seller_chat_id = seller_info_res.data[0]['chat_id']
            buyer_name = f"{buyer_info_res.data[0]['first_name']} {buyer_info_res.data[0]['last_name']}"
            notification_text = f"یک درخواست خرید جدید برای پیشنهاد شما از طرف «{buyer_name}» ثبت شد. لطفاً برای مدیریت درخواست‌ها به سامانه مراجعه کنید."
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": seller_chat_id, "text": notification_text})
        return jsonify({"message": "درخواست شما با موفقیت ثبت و برای فروشنده ارسال شد."}), 201
    except Exception as e:
        return jsonify({"error": f"Purchase Request Error: {str(e)}"}), 500

@app.route('/api/approve-request', methods=['POST'])
def approve_request():
    data = request.get_json(silent=True)
    if not data: return jsonify({"error": "درخواست نامعتبر"}), 400
    request_id = data.get('request_id')
    seller_nid = data.get('seller_nid')
    if not all([request_id, seller_nid]):
        return jsonify({"error": "اطلاعات ارسالی ناقص است."}), 400
    try:
        response = supabase.rpc('approve_purchase_request', { 'p_request_id': request_id, 'p_seller_national_id': seller_nid }).execute()
        if not response.data:
             return jsonify({"error": "خطایی در اجرای تابع پایگاه داده رخ داد."}), 500
        result = response.data[0]
        if result['status_code'] != 200:
            return jsonify({"error": result['message']}), result['status_code']
        buyer_chat_id = result.get('buyer_chat_id')
        seller_chat_id = result.get('seller_chat_id')
        buyer_phone = result.get('buyer_phone')
        seller_phone = result.get('seller_phone')
        if buyer_chat_id and seller_phone:
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": buyer_chat_id, "text": f"تبریک! درخواست خرید شما تایید شد.\nاطلاعات تماس فروشنده: {seller_phone}"})
        if seller_chat_id and buyer_phone:
             requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": seller_chat_id, "text": f"شما درخواست خرید را تایید کردید.\nاطلاعات تماس خریدار: {buyer_phone}"})
        return jsonify({"message": result['message']})
    except Exception as e:
        print(f"Approve Request Error: {e}")
        return jsonify({"error": "خطا در فرآیند تایید درخواست."}), 500

@app.route('/api/reject-request', methods=['POST'])
def reject_request():
    data = request.get_json(silent=True)
    if not data: return jsonify({"error": "درخواست نامعتبر"}), 400
    request_id = data.get('request_id')
    seller_nid = data.get('seller_nid')
    if not all([request_id, seller_nid]):
        return jsonify({"error": "اطلاعات ارسالی ناقص است."}), 400
    try:
        req_res = supabase.table('purchase_requests').select('*, sale_offers(seller_national_id)').eq('id', request_id).single().execute()
        if not req_res.data or req_res.data['sale_offers']['seller_national_id'] != seller_nid:
            return jsonify({"error": "شما اجازه رد این درخواست را ندارید."}), 403
        supabase.table('purchase_requests').update({'status': 'rejected'}).eq('id', request_id).execute()
        buyer_national_id = req_res.data['buyer_national_id']
        buyer_info_res = supabase.table('member').select('chat_id').eq('nationalcode', buyer_national_id).execute()
        if buyer_info_res.data and buyer_info_res.data[0].get('chat_id'):
            buyer_chat_id = buyer_info_res.data[0]['chat_id']
            notification_text = "متاسفانه درخواست خرید شما برای یک سهم، توسط فروشنده رد شد."
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": buyer_chat_id, "text": notification_text})
        return jsonify({"message": "درخواست با موفقیت رد شد."})
    except Exception as e:
        print(f"Reject Request Error: {e}")
        return jsonify({"error": "خطا در فرآیند رد کردن درخواست."}), 500

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
            otp_message = (f"ثبت‌نام شما با موفقیت انجام شد.\n\n*تعاونی مصرف کارکنان سازمان حج و زیارت*\n\nسهامدار گرامی، کد محرمانه زیر جهت ورود به سامانه تعاونی مصرف می‌باشد.\n*لطفاً این کد را در اختیار دیگران قرار ندهید.*\n\nکد ورود شما: `{otp_code}`")
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
                "chat_id": chat_id, "text": "برای تکمیل ثبت‌نام اولیه، لطفاً روی دکمه زیر کلیک کرده و شماره موبایل خود را با ما به اشتراک بگذارید.",
                "reply_markup": {"keyboard": [[{"text": "🔒 اشتراک‌گذاری شماره موبایل", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}
            }
            requests.post(f"{BALE_API_URL}/sendMessage", json=payload)
    return "ok", 200

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    national_id, otp_code = data.get('national_id'), data.get('otp_code')
    if not all([national_id, otp_code]): return jsonify({"error": "اطلاعات ناقص است."}), 400
    if national_id not in otp_storage:
        return jsonify({"error": "فرآیند ورود یافت نشد."}), 404
    stored_otp = otp_storage[national_id]
    if time.time() - stored_otp["timestamp"] > OTP_EXPIRATION_SECONDS:
        del otp_storage[national_id]
        return jsonify({"error": "کد تایید منقضی شده است."}), 410
    if stored_otp["code"] == otp_code:
        del otp_storage[national_id]
        try:
            response = supabase.table('member').select("address, postal_code").eq('nationalcode', national_id).execute()
            if response.data:
                user_profile = response.data[0]
                if user_profile.get('address') and user_profile.get('postal_code'):
                    return jsonify({"message": "ورود موفقیت‌آمیز بود!", "action": "go_to_dashboard"})
                else:
                    return jsonify({"message": "ورود موفقیت‌آمیز بود!", "action": "go_to_profile"})
            else:
                 return jsonify({"message": "ورود موفقیت‌آمیز بود!", "action": "go_to_profile"})
        except Exception as e:
            print(f"Profile check error: {e}")
            return jsonify({"message": "ورود موفقیت‌آمیز بود!", "action": "go_to_profile"})
    else:
        return jsonify({"error": "کد وارد شده صحیح نیست."}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)