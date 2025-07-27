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

# ---- بررسی امنیتی اولیه ----
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
AVERAGE_PRICE_THRESHOLD = 1000000  # حد متوسط قیمت (تومان در هر درصد)

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
@app.route('/admin_dashboard.html')
def serve_admin_dashboard(): return send_from_directory(app.static_folder, 'admin_dashboard.html')
@app.route('/offer_requests.html')
def serve_offer_requests(): return send_from_directory(app.static_folder, 'offer_requests.html')
@app.route('/health-check')
def health_check(): 
    print("Health check requested")
    return '', 204

# --- API Endpoints ---
@app.route('/api/admin-data')
def get_admin_data():
    try:
        offers = supabase.table('sale_offers').select('*, member:seller_national_id (first_name, last_name)').execute()
        requests = supabase.table('purchase_requests').select('*').execute()  # فقط درخواست‌ها رو بگیر
        for req in requests.data:
            buyer = supabase.table('member').select('first_name, last_name, phonenumber').eq('nationalcode', req['buyer_national_id']).execute()
            if buyer.data:
                req['member:buyer_national_id'] = buyer.data[0]
        print("Admin data requests raw:", requests.data)
        for req in requests.data:
            buyer_data = req.get('member:buyer_national_id', {})
            print(f"Request ID: {req.get('id')}, Buyer data: {buyer_data}, Buyer NID: {req.get('buyer_national_id')}")
            if not buyer_data:
                print(f"Warning: No buyer data for request ID: {req.get('id')}, buyer_national_id: {req.get('buyer_national_id')}, possible duplicate phonenumber or chat_id conflict")
        return jsonify({"offers": offers.data, "requests": requests.data})
    except Exception as e:
        print(f"Admin Data Error: {e}")
        return jsonify({"error": "خطا در دریافت داده‌ها."}), 500
    
@app.route('/api/start-login', methods=['POST'])
def start_login():
    try:
        data = request.get_json(silent=True)
        if not data or data.get('honeypot'): return jsonify({"error": "درخواست نامعتبر است."}), 400
        national_id = data.get('national_id')
        if not national_id: return jsonify({"error": "کد ملی الزامی است"}), 400
        response = supabase.table('member').select("phonenumber, chat_id").eq('nationalcode', national_id).execute()
        if not response.data: return jsonify({"error": "کاربر یافت نشد."}), 404
        user = response.data[0]
        if user.get('phonenumber') and user.get('chat_id'):
            otp_code = random.randint(10000, 99999)
            supabase.table('otp_codes').upsert({"national_id": national_id, "otp_code": str(otp_code), "timestamp": time.time()}).execute()
            otp_message = f"*تعاونی مصرف کارکنان سازمان حج و زیارت*\n\nسهامدار گرامی، کد محرمانه زیر جهت ورود به سامانه تعاونی مصرف می‌باشد. *لطفاً این کد را در اختیار دیگران قرار ندهید.*\nکد ورود شما: {otp_code}"
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": user['chat_id'], "text": otp_message, "parse_mode": "Markdown"})
            return jsonify({"action": "verify_otp"})
        else:
            token = secrets.token_urlsafe(16)
            linking_tokens[token] = national_id
            return jsonify({"action": "register", "linking_token": token})
    except Exception as e:
        print(f"Login Error: {e}")
        return jsonify({"error": "خطا در ورود."}), 500

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json()
        national_id, otp_code = data.get('national_id'), data.get('otp_code')
        if not all([national_id, otp_code]): return jsonify({"error": "اطلاعات ناقص است."}), 400
        response = supabase.table('otp_codes').select("*").eq('national_id', national_id).execute()
        if not response.data: return jsonify({"error": "فرآیند ورود یافت نشد."}), 404
        stored_otp = response.data[0]
        if time.time() - stored_otp["timestamp"] > OTP_EXPIRATION_SECONDS: 
            supabase.table('otp_codes').delete().eq('national_id', national_id).execute()
            return jsonify({"error": "کد تأیید منقضی شده است."}), 410
        if stored_otp["otp_code"] == otp_code:
            supabase.table('otp_codes').delete().eq('national_id', national_id).execute()
            profile = supabase.table('member').select("address, postal_code").eq('nationalcode', national_id).execute()
            if profile.data and profile.data[0].get('address') and profile.data[0].get('postal_code'):
                return jsonify({"message": "ورود موفق", "action": "go_to_dashboard"})
            else:
                return jsonify({"message": "ورود موفق", "action": "go_to_profile"})
        return jsonify({"error": "کد وارد شده صحیح نیست."}), 400
    except Exception as e:
        print(f"Verify OTP Error: {e}")
        return jsonify({"error": "خطا در تأیید."}), 500

@app.route('/api/update-profile', methods=['POST'])
def update_profile():
    try:
        data = request.get_json(silent=True)
        if not data: return jsonify({"error": "درخواست نامعتبر است."}), 400
        national_id, postal_code, address = data.get('national_id'), data.get('postal_code'), data.get('address')
        if not all([national_id, postal_code, address]) or not postal_code or not address:
            return jsonify({"error": "تمامی فیلدها الزامی هستند."}), 400
        supabase.table('member').update({"postal_code": postal_code, "address": address}).eq('nationalcode', national_id).execute()
        return jsonify({"message": "پروفایل به‌روز شد", "action": "go_to_dashboard"})
    except Exception as e:
        print(f"Profile Update Error: {e}")
        return jsonify({"error": "خطا در به‌روزرسانی."}), 500

@app.route('/api/dashboard-data')
def get_dashboard_data():
    try:
        national_id = request.args.get('nid')
        if not national_id: return jsonify({"error": "کد ملی ارسال نشده است."}), 400
        member = supabase.table('member').select("share_percentage, first_name, last_name").eq('nationalcode', national_id).execute()
        if not member.data: return jsonify({"error": "کاربر یافت نشد."}), 404
        share = member.data[0].get('share_percentage', 100)
        offers = supabase.table('sale_offers').select('percentage_to_sell').eq('seller_national_id', national_id).eq('status', 'active').execute()
        listed = sum(offer['percentage_to_sell'] for offer in offers.data) if offers.data else 0
        available = max(0, share - listed)
        return jsonify({"share_percentage": share, "available_share": available, "first_name": member.data[0]['first_name'], "last_name": member.data[0]['last_name']})
    except Exception as e:
        print(f"Dashboard Data Error: {e}")
        return jsonify({"error": "خطا در دریافت داده‌ها."}), 500

@app.route('/api/sell-share', methods=['POST'])
def sell_share():
    try:
        data = request.get_json(silent=True)
        if not data: return jsonify({"error": "درخواست نامعتبر است."}), 400
        national_id, percentage, price = data.get('national_id'), data.get('percentage_to_sell'), data.get('price')
        if not all([national_id, percentage, price]): return jsonify({"error": "اطلاعات ناقص است."}), 400
        member = supabase.table('member').select("share_percentage").eq('nationalcode', national_id).execute()
        if not member.data: return jsonify({"error": "کاربر یافت نشد."}), 404
        total_share = member.data[0].get('share_percentage', 100)
        offers = supabase.table('sale_offers').select('percentage_to_sell').eq('seller_national_id', national_id).eq('status', 'active').execute()
        listed = sum(offer['percentage_to_sell'] for offer in offers.data) if offers.data else 0
        if (listed + percentage) > total_share:
            return jsonify({"error": f"سهم کافی نیست. حداکثر {total_share - listed}% قابل فروش است."}), 400
        supabase.table('sale_offers').insert({"seller_national_id": national_id, "percentage_to_sell": percentage, "price": price, "status": "active"}).execute()
        return jsonify({"message": "پیشنهاد فروش ثبت شد."})
    except Exception as e:
        print(f"Sell Share Error: {e}")
        return jsonify({"error": "خطا در ثبت پیشنهاد."}), 500

@app.route('/api/sale-offers')
def get_sale_offers():
    try:
        offers = supabase.table('sale_offers').select('*, member:seller_national_id (first_name, last_name)').eq('status', 'active').execute()
        if offers.data:
            sorted_offers = sorted(offers.data, key=lambda x: (x.get('price', 0) / x.get('percentage_to_sell', 1) if x.get('percentage_to_sell', 1) > 0 else float('inf')))
            for offer in sorted_offers:
                normalized_price = (offer['price'] / offer['percentage_to_sell']) * 100 if offer['percentage_to_sell'] > 0 else 0
                offer['is_unusual'] = normalized_price > AVERAGE_PRICE_THRESHOLD
            return jsonify(sorted_offers)
        return jsonify([])
    except Exception as e:
        print(f"Get Offers Error: {e}")
        return jsonify({"error": "خطا در دریافت پیشنهادات."}), 500

@app.route('/api/offer-detail/<int:offer_id>', methods=['POST'])
def offer_detail(offer_id):
    try:
        data = request.get_json(silent=True)
        buyer_nid = data.get('buyer_nid')
        if not buyer_nid: return jsonify({"error": "کد ملی خریدار ارسال نشده است."}), 400
        offer = supabase.table('sale_offers').select('seller_national_id, percentage_to_sell, price, status').eq('id', offer_id).eq('status', 'active').execute()
        if not offer.data: return jsonify({"error": "پیشنهاد یافت نشد."}), 404
        offer_data = offer.data[0]
        if offer_data['seller_national_id'] == buyer_nid:
            return jsonify({"error": "نمی‌توانید پیشنهاد خود را بخرید."}), 400
        buyer = supabase.table('member').select('phonenumber, first_name, last_name').eq('nationalcode', buyer_nid).execute()
        if not buyer.data:
            print(f"No buyer data found for national_id: {buyer_nid}")
            return jsonify({"error": "اطلاعات خریدار یافت نشد."}), 404
        buyer_data = buyer.data[0]
        buyer_phone = buyer_data.get('phonenumber', 'شماره موجود نیست')
        message = f"کاربر {buyer_data.get('first_name', 'نامشخص')} {buyer_data.get('last_name', '')} (شماره: {buyer_phone}) تمایل به خرید {offer_data['percentage_to_sell']}% سهم شما با قیمت {offer_data['price']} تومان دارد."
        supabase.table('purchase_requests').insert({"offer_id": offer_id, "buyer_national_id": buyer_nid, "status": "pending"}).execute()
        seller = supabase.table('member').select('chat_id').eq('nationalcode', offer_data['seller_national_id']).execute()
        if seller.data and seller.data[0].get('chat_id'):
            requests.post(f"{BALE_API_URL}/sendMessage", json={"chat_id": seller.data[0]['chat_id'], "text": message})
        return jsonify({"message": "درخواست ثبت شد.", "offer": offer_data})
    except Exception as e:
        print(f"Offer Detail Error: {e}")
        return jsonify({"error": "خطا در پردازش."}), 500

@app.route('/api/cancel-offer/<int:offer_id>', methods=['POST'])
def cancel_offer(offer_id):
    try:
        data = request.get_json(silent=True)
        national_id = data.get('national_id')
        if not national_id: return jsonify({"error": "کد ملی ارسال نشده است."}), 400
        offer = supabase.table('sale_offers').select('seller_national_id, status').eq('id', offer_id).execute()
        if not offer.data: return jsonify({"error": "پیشنهاد یافت نشد."}), 404
        if offer.data[0]['seller_national_id'] != national_id: return jsonify({"error": "شما مجاز به لغو این پیشنهاد نیستید."}), 403
        if offer.data[0]['status'] != 'active': return jsonify({"error": "این پیشنهاد قابل لغو نیست."}), 400
        supabase.table('sale_offers').update({'status': 'cancelled'}).eq('id', offer_id).execute()
        return jsonify({"message": "پیشنهاد با موفقیت لغو شد."})
    except Exception as e:
        print(f"Cancel Offer Error: {e}")
        return jsonify({"error": "خطا در لغو پیشنهاد."}), 500

@app.route('/api/approve-request/<int:request_id>', methods=['POST'])
def approve_request(request_id):
    try:
        data = request.get_json(silent=True)
        seller_nid = data.get('seller_nid')
        if not seller_nid: return jsonify({"error": "کد ملی فروشنده ارسال نشده است."}), 400
        request = supabase.table('purchase_requests').select('offer_id, buyer_national_id, status').eq('id', request_id).execute()
        if not request.data: return jsonify({"error": "درخواست یافت نشد."}), 404
        if request.data[0]['status'] != 'pending': return jsonify({"error": "این درخواست قابل تأیید نیست."}), 400
        offer = supabase.table('sale_offers').select('seller_national_id, percentage_to_sell, status').eq('id', request.data[0]['offer_id']).execute()
        if not offer.data or offer.data[0]['seller_national_id'] != seller_nid: return jsonify({"error": "شما مجاز به تأیید این درخواست نیستید."}), 403
        supabase.table('purchase_requests').update({'status': 'approved'}).eq('id', request_id).execute()
        supabase.table('sale_offers').update({'status': 'sold'}).eq('id', request.data[0]['offer_id']).execute()
        return jsonify({"message": "درخواست با موفقیت تأیید شد."})
    except Exception as e:
        print(f"Approve Request Error: {e}")
        return jsonify({"error": "خطا در تأیید درخواست."}), 500

@app.route('/api/reject-request/<int:request_id>', methods=['POST'])
def reject_request(request_id):
    try:
        data = request.get_json(silent=True)
        seller_nid = data.get('seller_nid')
        if not seller_nid: return jsonify({"error": "کد ملی فروشنده ارسال نشده است."}), 400
        request = supabase.table('purchase_requests').select('offer_id, buyer_national_id, status').eq('id', request_id).execute()
        if not request.data: return jsonify({"error": "درخواست یافت نشد."}), 404
        if request.data[0]['status'] != 'pending': return jsonify({"error": "این درخواست قابل رد نیست."}), 400
        offer = supabase.table('sale_offers').select('seller_national_id, status').eq('id', request.data[0]['offer_id']).execute()
        if not offer.data or offer.data[0]['seller_national_id'] != seller_nid: return jsonify({"error": "شما مجاز به رد این درخواست نیستید."}), 403
        supabase.table('purchase_requests').update({'status': 'rejected'}).eq('id', request_id).execute()
        supabase.table('sale_offers').update({'status': 'active'}).eq('id', request.data[0]['offer_id']).execute()
        return jsonify({"message": "درخواست با موفقیت رد شد."})
    except Exception as e:
        print(f"Reject Request Error: {e}")
        return jsonify({"error": "خطا در رد درخواست."}), 500

@app.route('/api/admin-data')
def get_admin_data():
    try:
        offers = supabase.table('sale_offers').select('*, member:seller_national_id (first_name, last_name)').execute()
        requests = supabase.table('purchase_requests').select('*, sale_offers(seller_national_id, percentage_to_sell, price), member:buyer_national_id (first_name, last_name, phonenumber)').execute()
        print("Admin data requests raw:", requests.data)
        for req in requests.data:
            buyer_data = req.get('member:buyer_national_id', {})
            print(f"Request ID: {req.get('id')}, Buyer data: {buyer_data}, Buyer NID: {req.get('buyer_national_id')}")
            if not buyer_data:
                print(f"Warning: No buyer data for request ID: {req.get('id')}, buyer_national_id: {req.get('buyer_national_id')}, possible duplicate phonenumber or chat_id conflict")
        return jsonify({"offers": offers.data, "requests": requests.data})
    except Exception as e:
        print(f"Admin Data Error: {e}")
        return jsonify({"error": "خطا در دریافت داده‌ها."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port)