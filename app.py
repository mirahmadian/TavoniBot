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
    national_id = request.args.get('nid