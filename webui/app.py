#!/usr/bin/env python3
"""
EarnApp Bot Web UI - Flask Backend
Web interface untuk mengontrol EarnApp di multiple device
"""
import os
import sys
from flask import Flask, render_template, jsonify, request
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
    set_auto_restart as set_auto_restart_use_case,
    start_all_devices as start_all_devices_use_case,
    start_device as start_device_use_case,
    stop_all_devices as stop_all_devices_use_case,
    stop_device as stop_device_use_case,
)

app = Flask(__name__, template_folder=os.path.join(WEBUI_DIR, 'templates'), 
            static_folder=os.path.join(WEBUI_DIR, 'static'))
CORS(app)

storage = JsonStorage()

# Load konfigurasi
def load_config():
    return storage.load_config()

config = load_config()
ADMIN_ID = config.get("admin_telegram_id", "")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/devices', methods=['GET'])
def get_devices():
    return jsonify(list_devices_use_case(storage))

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
    return jsonify(start_device_use_case(storage, device_name))

@app.route('/api/devices/<device_name>/stop', methods=['POST'])
def stop_device(device_name):
    return jsonify(stop_device_use_case(storage, device_name))

@app.route('/api/devices/<device_name>/restart', methods=['POST'])
def restart_device(device_name):
    return jsonify(restart_device_use_case(storage, device_name))

@app.route('/api/devices/all/start', methods=['POST'])
def start_all_devices():
    return jsonify(start_all_devices_use_case(storage))

@app.route('/api/devices/all/stop', methods=['POST'])
def stop_all_devices():
    return jsonify(stop_all_devices_use_case(storage))

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
    import os
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
