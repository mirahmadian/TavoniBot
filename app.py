# app.py - DEBUGGING VERSION
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/profile.html')
def serve_profile():
    return send_from_directory(app.static_folder, 'profile.html')

# --- مسیر ویژه دیباگ ---
@app.route('/generate-linking-token', methods=['POST'])
def generate_linking_token_debug():
    try:
        # ما تمام اطلاعات ممکن را از درخواست استخراج می‌کنیم
        json_data = request.get_json(silent=True)
        form_data = request.form.to_dict()
        raw_data = request.data.decode('utf-8')
        headers = dict(request.headers)

        # یک بسته اطلاعاتی برای ارسال به فرانت‌اند می‌سازیم
        debug_info = {
            "message": "DEBUGGING_INFORMATION",
            "is_json_request": request.is_json,
            "json_data": json_data,
            "form_data": form_data,
            "raw_data_body": raw_data,
            "headers": headers
        }
        # این بسته را با کد موفقیت 200 برمی‌گردانیم تا فرانت‌اند آن را پردازش کند
        return jsonify(debug_info), 200

    except Exception as e:
        return jsonify({"error": f"Error during debug: {str(e)}"}), 500