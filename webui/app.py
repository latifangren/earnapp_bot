#!/usr/bin/env python3
"""
EarnApp Bot Web UI - Flask Backend
Web interface untuk mengontrol EarnApp di multiple device
"""
import os
import json
import time
import subprocess
import paramiko
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime

# Get webui directory for Flask templates/static
WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(WEBUI_DIR, 'templates'), 
            static_folder=os.path.join(WEBUI_DIR, 'static'))
CORS(app)

# Get root directory (parent of webui folder)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load konfigurasi
def load_config():
    config_file = os.path.join(ROOT_DIR, "config.json")
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return json.load(f)
    return {}

config = load_config()
ADMIN_ID = config.get("admin_telegram_id", "")

# ADB Configuration
EARN_APP_PACKAGE = "com.brd.earnrewards"
EARN_APP_ACTIVITY = "com.brd.earnrewards/.ConsentActivity"

# File paths (relative to root directory)
DEVICE_FILE = os.path.join(ROOT_DIR, "devices.json")
SCHEDULE_FILE = os.path.join(ROOT_DIR, "schedules.json")
AUTO_RESTART_FILE = os.path.join(ROOT_DIR, "auto_restart.json")
ACTIVITY_LOG_FILE = os.path.join(ROOT_DIR, "activity_log.json")

# Load data dari file
def load_devices():
    if os.path.exists(DEVICE_FILE):
        with open(DEVICE_FILE, "r") as f:
            return json.load(f)
    return {"Local": {"type": "local", "path": "/usr/bin"}}

def save_devices(devices_data):
    with open(DEVICE_FILE, "w") as f:
        json.dump(devices_data, f, indent=2)

def load_schedules():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "r") as f:
            return json.load(f)
    return {}

def load_auto_restart():
    if os.path.exists(AUTO_RESTART_FILE):
        with open(AUTO_RESTART_FILE, "r") as f:
            return json.load(f)
    return {}

def load_activity_logs():
    if os.path.exists(ACTIVITY_LOG_FILE):
        with open(ACTIVITY_LOG_FILE, "r") as f:
            return json.load(f)
    return []

def save_activity_logs(logs):
    with open(ACTIVITY_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

# Command execution functions
def run_cmd_local(cmd):
    try:
        if cmd.startswith("earnapp"):
            which_result = subprocess.run("which earnapp", shell=True, capture_output=True, text=True)
            if which_result.returncode == 0:
                earnapp_path = which_result.stdout.strip()
                if cmd.startswith("earnapp "):
                    cmd = cmd.replace("earnapp ", f"{earnapp_path} ", 1)
                elif cmd.strip() == "earnapp":
                    cmd = earnapp_path
            else:
                return "❌ EarnApp tidak ditemukan di sistem."
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        return out.strip()
    except subprocess.CalledProcessError as e:
        return (e.output or str(e)).strip()

def run_cmd_ssh(host, port, username, password, cmd, timeout=20):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, port=port, username=username, password=password, timeout=timeout)
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        ssh.close()
        combined = (out + ("\n" + err if err else "")).strip()
        return combined if combined else "(no output)"
    except Exception as e:
        return f"❌ SSH error: {e}"

def run_cmd_adb(host, port, cmd, timeout=20):
    try:
        connect_cmd = f"adb connect {host}:{port}"
        subprocess.run(connect_cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        
        if cmd.startswith("shell "):
            adb_cmd = f"adb -s {host}:{port} {cmd}"
        else:
            adb_cmd = f"adb -s {host}:{port} shell {cmd}"
        
        result = subprocess.run(adb_cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        output = result.stdout.strip()
        error = result.stderr.strip()
        combined = (output + ("\n" + error if error else "")).strip()
        return combined if combined else "(no output)"
    except subprocess.TimeoutExpired:
        return f"❌ ADB timeout: Command melebihi {timeout} detik"
    except Exception as e:
        return f"❌ ADB error: {e}"

def run_cmd_device_by_name(device_name, cmd):
    devices = load_devices()
    if device_name not in devices:
        return f"❌ Device '{device_name}' tidak ditemukan."

    dev = devices[device_name]
    if dev["type"] == "local":
        path = dev.get("path", ".")
        full_cmd = f"cd {path} && {cmd}"
        return run_cmd_local(full_cmd)
    elif dev["type"] == "ssh":
        host = dev.get("host")
        port = dev.get("port", 22)
        user = dev.get("user")
        password = dev.get("password")
        return run_cmd_ssh(host, port, user, password, cmd)
    elif dev["type"] == "adb":
        host = dev.get("host")
        port = dev.get("port", 5555)
        return run_cmd_adb(host, port, cmd)
    else:
        return "❌ Tipe device tidak dikenali."

def get_ssh_earnapp_status(device_name):
    devices = load_devices()
    if device_name not in devices:
        return None
    
    dev = devices[device_name]
    if dev.get("type") not in ["ssh", "local"]:
        return None
    
    try:
        status_cmd = "earnapp status"
        status_result = run_cmd_device_by_name(device_name, status_cmd)
        
        if status_result and "error" not in status_result.lower():
            status_lower = status_result.lower()
            if "status: enabled" in status_lower or "status: running" in status_lower or "enabled" in status_lower:
                return "🟢 Running"
            elif "status: disabled" in status_lower or "status: stopped" in status_lower or "disabled" in status_lower:
                return "🔴 Stopped"
        
        cmd = "pgrep -f earnapp || ps aux | grep -i earnapp | grep -v grep"
        result = run_cmd_device_by_name(device_name, cmd)
        
        if result and result.strip() and "error" not in result.lower():
            status_cmd2 = "earnapp status 2>&1"
            status_result2 = run_cmd_device_by_name(device_name, status_cmd2)
            if status_result2:
                status_lower2 = status_result2.lower()
                if "disabled" in status_lower2:
                    return "🔴 Stopped"
                elif "enabled" in status_lower2 or "running" in status_lower2:
                    return "🟢 Running"
        
        check_cmd = "which earnapp || command -v earnapp"
        check_result = run_cmd_device_by_name(device_name, check_cmd)
        
        if check_result and "earnapp" in check_result and "error" not in check_result.lower():
            return "🔴 Stopped"
        else:
            return "❌ Not installed"
    except Exception as e:
        return f"❌ Error: {str(e)[:50]}"

def get_adb_app_status(device_name):
    devices = load_devices()
    if device_name not in devices:
        return "❌ Device tidak ditemukan"
    
    dev = devices[device_name]
    if dev.get("type") != "adb":
        return None
    
    try:
        cmd = f"pidof {EARN_APP_PACKAGE}"
        result = run_cmd_device_by_name(device_name, cmd)
        
        if result and result.strip() and not "error" in result.lower() and result.strip().isdigit():
            return "🟢 Running"
        else:
            check_cmd = f"pm list packages | grep {EARN_APP_PACKAGE}"
            check_result = run_cmd_device_by_name(device_name, check_cmd)
            if EARN_APP_PACKAGE in check_result:
                return "🔴 Stopped"
            else:
                return "❌ Not installed"
    except Exception as e:
        return f"❌ Error: {str(e)[:50]}"

def format_adb_result(action, result, device_name):
    if not result or result == "(no output)":
        if action == "start":
            status = get_adb_app_status(device_name)
            if status and "Running" in status:
                return f"✅ EarnApp berhasil dijalankan\n\nStatus: {status}"
            else:
                return f"⚠️ EarnApp mungkin sudah berjalan atau ada masalah\n\nStatus: {status or 'Unknown'}"
        elif action == "stop":
            status = get_adb_app_status(device_name)
            if status and "Stopped" in status:
                return f"✅ EarnApp berhasil dihentikan\n\nStatus: {status}"
            else:
                return f"⚠️ EarnApp mungkin masih berjalan\n\nStatus: {status or 'Unknown'}"
        else:
            return "✅ Command berhasil dijalankan"
    
    result_lower = result.lower()
    if "error" in result_lower or "failed" in result_lower or "❌" in result:
        return f"❌ Error: {result[:200]}"
    elif "starting" in result_lower or "started" in result_lower:
        status = get_adb_app_status(device_name)
        return f"✅ EarnApp berhasil dijalankan\n\nStatus: {status}"
    else:
        status = get_adb_app_status(device_name)
        if action == "start":
            return f"✅ EarnApp berhasil dijalankan\n\nStatus: {status}"
        elif action == "stop":
            return f"✅ EarnApp berhasil dihentikan\n\nStatus: {status}"
        else:
            return f"✅ Command berhasil\n\nStatus: {status}"

def start_earnapp_device(device_name):
    devices = load_devices()
    if device_name not in devices:
        return f"❌ Device '{device_name}' tidak ditemukan."
    
    dev = devices[device_name]
    if dev.get("type") == "adb":
        cmd = f"am start -n {EARN_APP_ACTIVITY}"
        result = run_cmd_device_by_name(device_name, cmd)
        return format_adb_result("start", result, device_name)
    else:
        return run_cmd_device_by_name(device_name, "earnapp start")

def stop_earnapp_device(device_name):
    devices = load_devices()
    if device_name not in devices:
        return f"❌ Device '{device_name}' tidak ditemukan."
    
    dev = devices[device_name]
    if dev.get("type") == "adb":
        cmd = f"am force-stop {EARN_APP_PACKAGE}"
        result = run_cmd_device_by_name(device_name, cmd)
        return format_adb_result("stop", result, device_name)
    else:
        return run_cmd_device_by_name(device_name, "earnapp stop")

def check_device_health(device_name):
    devices = load_devices()
    try:
        dev = devices.get(device_name)
        if not dev:
            return False
        
        if dev.get("type") == "adb":
            result = run_cmd_device_by_name(device_name, "getprop ro.build.version.release")
        else:
            result = run_cmd_device_by_name(device_name, "echo 'health_check'")
        
        if result and "error" not in result.lower() and result.strip():
            return True
        else:
            return False
    except Exception:
        return False

def log_activity(device_name, action, result, log_type="manual", user="web"):
    try:
        logs = load_activity_logs()
        log_entry = {
            "timestamp": int(time.time()),
            "device": device_name,
            "action": action,
            "result": result[:500] if result else "",
            "type": log_type,
            "user": user
        }
        
        logs.append(log_entry)
        
        # Keep only last 1000 entries
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        save_activity_logs(logs)
    except Exception as e:
        print(f"Error logging activity: {e}")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/devices', methods=['GET'])
def get_devices():
    devices = load_devices()
    return jsonify({"devices": devices})

@app.route('/api/devices', methods=['POST'])
def add_device():
    data = request.json
    devices = load_devices()
    
    device_name = data.get("name")
    device_type = data.get("type")
    
    if device_type == "ssh":
        devices[device_name] = {
            "type": "ssh",
            "host": data.get("host"),
            "port": data.get("port", 22),
            "user": data.get("user"),
            "password": data.get("password")
        }
    elif device_type == "adb":
        devices[device_name] = {
            "type": "adb",
            "host": data.get("host"),
            "port": data.get("port", 5555)
        }
    elif device_type == "local":
        devices[device_name] = {
            "type": "local",
            "path": data.get("path", "/usr/bin")
        }
    
    save_devices(devices)
    return jsonify({"success": True, "message": f"Device '{device_name}' berhasil ditambahkan"})

@app.route('/api/devices/<device_name>', methods=['DELETE'])
def delete_device(device_name):
    devices = load_devices()
    if device_name in devices:
        del devices[device_name]
        save_devices(devices)
        return jsonify({"success": True, "message": f"Device '{device_name}' berhasil dihapus"})
    return jsonify({"success": False, "message": "Device tidak ditemukan"}), 404

@app.route('/api/devices/<device_name>/status', methods=['GET'])
def get_device_status(device_name):
    devices = load_devices()
    if device_name not in devices:
        return jsonify({"error": "Device tidak ditemukan"}), 404
    
    dev = devices[device_name]
    is_healthy = check_device_health(device_name)
    
    if dev.get("type") == "adb":
        earnapp_status = get_adb_app_status(device_name)
    else:
        earnapp_status = get_ssh_earnapp_status(device_name)
    
    if earnapp_status and "Running" in earnapp_status:
        status_icon = "🟢"
        status_text = "Running"
    elif earnapp_status and "Stopped" in earnapp_status:
        status_icon = "🔴"
        status_text = "Stopped"
    elif earnapp_status and "Not installed" in earnapp_status:
        status_icon = "❌"
        status_text = "Not installed"
    else:
        status_icon = "⚠️"
        status_text = earnapp_status or "Unknown"
    
    return jsonify({
        "device": device_name,
        "health": "online" if is_healthy else "offline",
        "earnapp_status": status_text,
        "status_icon": status_icon
    })

@app.route('/api/devices/all/status', methods=['GET'])
def get_all_devices_status():
    devices = load_devices()
    result = []
    
    for device_name in devices.keys():
        dev = devices[device_name]
        is_healthy = check_device_health(device_name)
        
        if dev.get("type") == "adb":
            earnapp_status = get_adb_app_status(device_name)
        else:
            earnapp_status = get_ssh_earnapp_status(device_name)
        
        if earnapp_status and "Running" in earnapp_status:
            status_icon = "🟢"
            status_text = "Running"
        elif earnapp_status and "Stopped" in earnapp_status:
            status_icon = "🔴"
            status_text = "Stopped"
        elif earnapp_status and "Not installed" in earnapp_status:
            status_icon = "❌"
            status_text = "Not installed"
        else:
            status_icon = "⚠️"
            status_text = earnapp_status or "Unknown"
        
        result.append({
            "name": device_name,
            "type": dev.get("type", "unknown"),
            "health": "online" if is_healthy else "offline",
            "earnapp_status": status_text,
            "status_icon": status_icon
        })
    
    return jsonify({"devices": result})

@app.route('/api/devices/<device_name>/start', methods=['POST'])
def start_device(device_name):
    result = start_earnapp_device(device_name)
    log_activity(device_name, "start", result, "manual", "web")
    return jsonify({"success": True, "result": result})

@app.route('/api/devices/<device_name>/stop', methods=['POST'])
def stop_device(device_name):
    result = stop_earnapp_device(device_name)
    log_activity(device_name, "stop", result, "manual", "web")
    return jsonify({"success": True, "result": result})

@app.route('/api/devices/<device_name>/restart', methods=['POST'])
def restart_device(device_name):
    stop_result = stop_earnapp_device(device_name)
    time.sleep(5)
    start_result = start_earnapp_device(device_name)
    result = f"Stop: {stop_result}\n\nStart: {start_result}"
    log_activity(device_name, "restart", result, "manual", "web")
    return jsonify({"success": True, "result": result})

@app.route('/api/devices/all/start', methods=['POST'])
def start_all_devices():
    devices = load_devices()
    results = []
    for device_name in devices.keys():
        result = start_earnapp_device(device_name)
        log_activity(device_name, "start", result, "manual", "web")
        results.append({"device": device_name, "result": result})
    return jsonify({"success": True, "results": results})

@app.route('/api/devices/all/stop', methods=['POST'])
def stop_all_devices():
    devices = load_devices()
    results = []
    for device_name in devices.keys():
        result = stop_earnapp_device(device_name)
        log_activity(device_name, "stop", result, "manual", "web")
        results.append({"device": device_name, "result": result})
    return jsonify({"success": True, "results": results})

@app.route('/api/devices/<device_name>/id', methods=['GET'])
def get_device_id(device_name):
    devices = load_devices()
    if device_name not in devices:
        return jsonify({"error": "Device tidak ditemukan"}), 404
    
    dev = devices[device_name]
    if dev.get("type") == "adb":
        cmd = "settings get secure android_id"
    else:
        cmd = "earnapp showid"
    
    result = run_cmd_device_by_name(device_name, cmd)
    return jsonify({"success": True, "result": result})

@app.route('/api/activity-logs', methods=['GET'])
def get_activity_logs():
    logs = load_activity_logs()
    device_filter = request.args.get('device')
    limit = int(request.args.get('limit', 100))
    
    filtered_logs = logs
    if device_filter:
        filtered_logs = [log for log in logs if log.get("device") == device_filter]
    
    filtered_logs = filtered_logs[-limit:]
    
    # Format timestamp
    for log in filtered_logs:
        timestamp = log.get("timestamp", 0)
        log["formatted_time"] = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify({"logs": filtered_logs})

@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    schedules = load_schedules()
    return jsonify({"schedules": schedules})

@app.route('/api/auto-restart', methods=['GET'])
def get_auto_restart():
    auto_restart = load_auto_restart()
    return jsonify({"auto_restart": auto_restart})

@app.route('/api/auto-restart/<device_name>', methods=['POST'])
def set_auto_restart(device_name):
    data = request.json
    auto_restart = load_auto_restart()
    
    interval = float(data.get("interval_hours", 6))
    if interval < 0.5 or interval > 168:
        return jsonify({"success": False, "message": "Interval harus antara 0.5-168 jam"}), 400
    
    auto_restart[device_name] = {
        "enabled": True,
        "interval_hours": interval,
        "delay_seconds": 5,
        "last_run": int(time.time())
    }
    
    with open(AUTO_RESTART_FILE, "w") as f:
        json.dump(auto_restart, f, indent=2)
    
    return jsonify({"success": True, "message": f"Auto restart untuk {device_name} berhasil diatur"})

@app.route('/api/auto-restart/<device_name>', methods=['DELETE'])
def disable_auto_restart(device_name):
    auto_restart = load_auto_restart()
    if device_name in auto_restart:
        auto_restart[device_name]["enabled"] = False
        with open(AUTO_RESTART_FILE, "w") as f:
            json.dump(auto_restart, f, indent=2)
        return jsonify({"success": True, "message": f"Auto restart untuk {device_name} dinonaktifkan"})
    return jsonify({"success": False, "message": "Device tidak ditemukan"}), 404

@app.route('/api/schedules', methods=['POST'])
def add_schedule():
    data = request.json
    schedules = load_schedules()
    
    device_name = data.get("device")
    action = data.get("action")  # start/stop/restart
    time_str = data.get("time")  # HH:MM
    days = data.get("days", [])  # [0,1,2,3,4,5,6]
    
    task_id = f"{device_name}_{time_str}_{action}"
    schedules[task_id] = {
        "device": device_name,
        "action": action,
        "time": time_str,
        "days": days,
        "enabled": True,
        "timezone": "UTC"
    }
    
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedules, f, indent=2)
    
    return jsonify({"success": True, "message": f"Schedule berhasil ditambahkan", "task_id": task_id})

@app.route('/api/schedules/<task_id>', methods=['DELETE'])
def delete_schedule(task_id):
    schedules = load_schedules()
    if task_id in schedules:
        del schedules[task_id]
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(schedules, f, indent=2)
        return jsonify({"success": True, "message": "Schedule berhasil dihapus"})
    return jsonify({"success": False, "message": "Schedule tidak ditemukan"}), 404

@app.route('/api/devices/all/health-check', methods=['POST'])
def health_check_all():
    devices = load_devices()
    results = []
    for device_name in devices.keys():
        is_healthy = check_device_health(device_name)
        results.append({
            "device": device_name,
            "health": "online" if is_healthy else "offline"
        })
    return jsonify({"success": True, "results": results})

if __name__ == '__main__':
    # Untuk production, gunakan systemd service
    # Untuk development, set debug=True
    import os
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)

