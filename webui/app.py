#!/usr/bin/env python3
"""
EarnApp Bot Web UI - Flask Backend
Web interface untuk mengontrol EarnApp di multiple device
"""
import binascii
import base64
import os
import secrets
import sys

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# Get webui directory for Flask templates/static
WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(WEBUI_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from earnapp.core.storage import JsonStorage
from earnapp.core.use_cases import (
    add_device as add_device_use_case,
    add_schedule as add_schedule_use_case,
    delete_device as delete_device_use_case,
    delete_schedule as delete_schedule_use_case,
    disable_auto_restart as disable_auto_restart_use_case,
    get_all_device_statuses as get_all_device_statuses_use_case,
    get_device_id as get_device_id_use_case,
    get_device_status as get_device_status_use_case,
    health_check_all as health_check_all_use_case,
    list_activity_logs as list_activity_logs_use_case,
    list_auto_restart as list_auto_restart_use_case,
    list_devices as list_devices_use_case,
    list_schedules as list_schedules_use_case,
    restart_device as restart_device_use_case,
    restart_all_devices as restart_all_devices_use_case,
    set_auto_restart as set_auto_restart_use_case,
    start_all_devices as start_all_devices_use_case,
    start_device as start_device_use_case,
    stop_all_devices as stop_all_devices_use_case,
    stop_device as stop_device_use_case,
)

app = Flask(__name__, template_folder=os.path.join(WEBUI_DIR, 'templates'), 
            static_folder=os.path.join(WEBUI_DIR, 'static'))

storage = JsonStorage()

# Load konfigurasi
def load_config():
    return storage.load_config()


config = load_config()
ADMIN_ID = config.get("admin_telegram_id", "")

def _load_webui_auth_config():
    username = os.getenv('WEBUI_AUTH_USERNAME')
    password = os.getenv('WEBUI_AUTH_PASSWORD')
    if username is None:
        username = config.get('webui_auth_username', 'admin')
    if password is None:
        password = config.get('webui_auth_password', '')
    return {
        'username': username or 'admin',
        'password': password or '',
    }


WEBUI_AUTH = _load_webui_auth_config()
WEBUI_CSRF_TOKEN = secrets.token_urlsafe(32)
WEBUI_CORS_ORIGINS = [origin.strip() for origin in os.getenv('WEBUI_CORS_ORIGINS', '').split(',') if origin.strip()]
if WEBUI_CORS_ORIGINS:
    CORS(app, resources={r'/api/*': {'origins': WEBUI_CORS_ORIGINS}})

SENSITIVE_DEVICE_KEYS = set(['password', 'token', 'secret', 'private_key', 'passphrase', 'api_key'])


def _is_protected_request():
    return request.path == '/' or request.path.startswith('/api/')


def _is_unsafe_api_request():
    return request.path.startswith('/api/') and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}


def _auth_missing_password_response():
    payload = {'success': False, 'error': 'Web UI authentication is not configured. Set WEBUI_AUTH_PASSWORD.'}
    if request.path.startswith('/api/'):
        return jsonify(payload), 503
    return payload['error'], 503


def _auth_required_response():
    payload = {'success': False, 'error': 'Authentication required.'}
    response = jsonify(payload)
    response.status_code = 401
    response.headers['WWW-Authenticate'] = 'Basic realm="EarnApp Web UI"'
    return response


def _csrf_required_response():
    return jsonify({'success': False, 'error': 'Invalid CSRF token.'}), 403


def _parse_basic_auth_header():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Basic '):
        return None, None
    try:
        encoded = auth_header.split(' ', 1)[1].strip()
        decoded = base64.b64decode(encoded).decode('utf-8')
        username, password = decoded.split(':', 1)
        return username, password
    except (TypeError, ValueError, UnicodeDecodeError, binascii.Error):
        return None, None


def _is_authorized():
    if not WEBUI_AUTH.get('password'):
        return False, 'missing_password'
    username, password = _parse_basic_auth_header()
    if username is None:
        return False, 'invalid'
    configured_username = str(WEBUI_AUTH.get('username', 'admin'))
    configured_password = str(WEBUI_AUTH.get('password', ''))
    username_ok = secrets.compare_digest(str(username), configured_username)
    password_ok = secrets.compare_digest(str(password), configured_password)
    return username_ok and password_ok, 'invalid'


def _scrub_sensitive_values(value):
    if isinstance(value, dict):
        scrubbed = {}
        for key, item in value.items():
            normalized_key = key.lower().replace('-', '_')
            if normalized_key in SENSITIVE_DEVICE_KEYS or any(token in normalized_key for token in SENSITIVE_DEVICE_KEYS):
                continue
            scrubbed[key] = _scrub_sensitive_values(item)
        return scrubbed
    if isinstance(value, list):
        return [_scrub_sensitive_values(item) for item in value]
    return value


def _jsonify_action(payload, failure_status=500):
    if isinstance(payload, dict) and not payload.get('message') and payload.get('result'):
        payload = dict(payload)
        payload['message'] = payload.get('result')
    if isinstance(payload, dict) and payload.get('success') is False:
        return jsonify(payload), failure_status
    return jsonify(payload)


@app.before_request
def _protect_webui():
    if not _is_protected_request():
        return None
    if request.method == 'OPTIONS' and request.path.startswith('/api/'):
        return None
    if not WEBUI_AUTH.get('password'):
        return _auth_missing_password_response()
    authorized, _ = _is_authorized()
    if not authorized:
        return _auth_required_response()
    if _is_unsafe_api_request():
        csrf_token = request.headers.get('X-CSRF-Token', '')
        if not secrets.compare_digest(str(csrf_token), WEBUI_CSRF_TOKEN):
            return _csrf_required_response()
    return None

# Routes
@app.route('/')
def index():
    return render_template('index.html', csrf_token=WEBUI_CSRF_TOKEN)

@app.route('/api/devices', methods=['GET'])
def get_devices():
    payload = list_devices_use_case(storage)
    payload['devices'] = _scrub_sensitive_values(payload.get('devices', {}))
    return jsonify(payload)

@app.route('/api/devices', methods=['POST'])
def add_device():
    data = request.json
    return jsonify(add_device_use_case(storage, data))

@app.route('/api/devices/<device_name>', methods=['DELETE'])
def delete_device(device_name):
    payload, status_code = delete_device_use_case(storage, device_name)
    if status_code == 200:
        return jsonify(payload)
    return jsonify(payload), status_code

@app.route('/api/devices/<device_name>/status', methods=['GET'])
def get_device_status(device_name):
    payload, status_code = get_device_status_use_case(storage, device_name)
    if status_code == 200:
        return jsonify(payload)
    return jsonify(payload), status_code

@app.route('/api/devices/all/status', methods=['GET'])
def get_all_devices_status():
    return jsonify(get_all_device_statuses_use_case(storage))

@app.route('/api/devices/<device_name>/start', methods=['POST'])
def start_device(device_name):
    return _jsonify_action(start_device_use_case(storage, device_name))

@app.route('/api/devices/<device_name>/stop', methods=['POST'])
def stop_device(device_name):
    return _jsonify_action(stop_device_use_case(storage, device_name))

@app.route('/api/devices/<device_name>/restart', methods=['POST'])
def restart_device(device_name):
    return _jsonify_action(restart_device_use_case(storage, device_name))

@app.route('/api/devices/all/restart', methods=['POST'])
def restart_all_devices():
    return _jsonify_action(restart_all_devices_use_case(storage))

@app.route('/api/devices/all/start', methods=['POST'])
def start_all_devices():
    return _jsonify_action(start_all_devices_use_case(storage))

@app.route('/api/devices/all/stop', methods=['POST'])
def stop_all_devices():
    return _jsonify_action(stop_all_devices_use_case(storage))

@app.route('/api/devices/<device_name>/id', methods=['GET'])
def get_device_id(device_name):
    payload, status_code = get_device_id_use_case(storage, device_name)
    if status_code == 200:
        return jsonify(payload)
    return jsonify(payload), status_code

@app.route('/api/activity-logs', methods=['GET'])
def get_activity_logs():
    device_filter = request.args.get('device')
    limit = int(request.args.get('limit', 100))
    return jsonify(list_activity_logs_use_case(storage, device_filter, limit))

@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    return jsonify(list_schedules_use_case(storage))

@app.route('/api/auto-restart', methods=['GET'])
def get_auto_restart():
    return jsonify(list_auto_restart_use_case(storage))

@app.route('/api/auto-restart/<device_name>', methods=['POST'])
def set_auto_restart(device_name):
    data = request.json
    payload, status_code = set_auto_restart_use_case(storage, device_name, data)
    if status_code == 200:
        return jsonify(payload)
    return jsonify(payload), status_code

@app.route('/api/auto-restart/<device_name>', methods=['DELETE'])
def disable_auto_restart(device_name):
    payload, status_code = disable_auto_restart_use_case(storage, device_name)
    if status_code == 200:
        return jsonify(payload)
    return jsonify(payload), status_code

@app.route('/api/schedules', methods=['POST'])
def add_schedule():
    data = request.json
    return jsonify(add_schedule_use_case(storage, data))

@app.route('/api/schedules/<task_id>', methods=['DELETE'])
def delete_schedule(task_id):
    payload, status_code = delete_schedule_use_case(storage, task_id)
    if status_code == 200:
        return jsonify(payload)
    return jsonify(payload), status_code

@app.route('/api/devices/all/health-check', methods=['POST'])
def health_check_all():
    return jsonify(health_check_all_use_case(storage))

if __name__ == '__main__':
    # Untuk production, gunakan systemd service
    # Untuk development, set debug=True
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    webui_port = os.getenv('WEBUI_PORT', '5000')
    try:
        webui_port = int(webui_port)
    except ValueError:
        webui_port = 5000
    app.run(host=os.getenv('WEBUI_HOST', '127.0.0.1'), port=webui_port, debug=debug_mode)
