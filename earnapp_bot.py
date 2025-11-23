#!/usr/bin/env python3
import os
import json
import telebot
import subprocess
from telebot import types
import paramiko
import time
import threading

# Load konfigurasi dari file
def load_config():
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return json.load(f)
    else:
        print("❌ File config.json tidak ditemukan!")
        print("📝 Buat file config.json dengan format:")
        print('{"bot_token": "YOUR_BOT_TOKEN", "admin_telegram_id": "YOUR_TELEGRAM_ID"}')
        exit(1)

config = load_config()
TOKEN = config.get("bot_token")
ADMIN_ID = config.get("admin_telegram_id")

if not TOKEN:
    print("❌ Bot token tidak ditemukan di config.json!")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# -----------------------
# ADB Configuration
# -----------------------
EARN_APP_PACKAGE = "com.brd.earnrewards"
EARN_APP_ACTIVITY = "com.brd.earnrewards/.ConsentActivity"

# -----------------------
# File untuk menyimpan device
# -----------------------
DEVICE_FILE = "devices.json"

# Load device dari JSON jika ada
if os.path.exists(DEVICE_FILE):
    with open(DEVICE_FILE, "r") as f:
        devices = json.load(f)
else:
    # Device default: lokal
    devices = {
        "Local": {"type": "local", "path": "/usr/bin"}
    }
    # Simpan file devices.json default
    with open(DEVICE_FILE, "w") as f:
        json.dump(devices, f, indent=2)

# Menyimpan device yang dipilih tiap chat_id
user_device = {}

# Menyimpan state sementara saat user menambah device
add_device_state = {}  # chat_id -> {"step":1..4, "data":{}}

# Menyimpan state sementara saat user ingin menghapus device
remove_device_state = {}  # chat_id -> True

# Menyimpan scheduled tasks (time-based)
SCHEDULE_FILE = "schedules.json"
scheduled_tasks = {}  # task_id -> {"device": "name", "action": "restart/start/stop", "time": "HH:MM", "days": [0,1,2,3,4,5,6], "enabled": True, "timezone": "UTC"}

# Load scheduled tasks dari file
if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r") as f:
            scheduled_tasks = json.load(f)
    except Exception as e:
        print(f"Error loading schedules.json: {e}")
        scheduled_tasks = {}

# Menyimpan state sementara saat user menambah time-based schedule
schedule_state = {}  # chat_id -> {"step": 1..5, "data": {}}

# Menyimpan state sementara saat user filter log by date
filter_date_state = {}  # chat_id -> True

# Menyimpan auto restart interval settings
AUTO_RESTART_FILE = "auto_restart.json"
auto_restart_settings = {}  # device_name -> {"enabled": True/False, "interval_hours": 6, "delay_seconds": 5, "last_run": timestamp}

# Load auto restart settings dari file
if os.path.exists(AUTO_RESTART_FILE):
    try:
        with open(AUTO_RESTART_FILE, "r") as f:
            auto_restart_settings = json.load(f)
    except Exception as e:
        print(f"Error loading auto_restart.json: {e}")
        auto_restart_settings = {}

# Menyimpan state sementara saat user mengatur auto restart
auto_restart_state = {}  # chat_id -> {"step": 1..3, "data": {}}

# Menyimpan device health status
device_health = {}  # device_name -> {"status": "online/offline", "last_check": timestamp, "error": "message"}

# Menyimpan alert settings
alert_settings = {
    "enabled": True,
    "offline_threshold": 300,  # 5 menit
    "check_interval": 60  # 1 menit
}

# Activity Log & History
ACTIVITY_LOG_FILE = "activity_log.json"
activity_logs = []  # List of logs: [{"timestamp": timestamp, "device": "name", "action": "start/stop/restart", "result": "result", "user": "admin", "type": "manual/auto/scheduled"}]

# Load activity logs dari file
if os.path.exists(ACTIVITY_LOG_FILE):
    try:
        with open(ACTIVITY_LOG_FILE, "r") as f:
            activity_logs = json.load(f)
    except Exception as e:
        print(f"Error loading activity_log.json: {e}")
        activity_logs = []

# Limit jumlah log (keep last 1000 entries)
MAX_LOG_ENTRIES = 1000

# -----------------------
# Fungsi menjalankan perintah
# -----------------------
def run_cmd_local(cmd):
    try:
        # Pakai path absolut ke earnapp untuk command yang mulai dengan 'earnapp'
        if cmd.startswith("earnapp"):
            which_result = subprocess.run("which earnapp", shell=True, capture_output=True, text=True)
            if which_result.returncode == 0:
                earnapp_path = which_result.stdout.strip()
                if cmd.startswith("earnapp "):
                    cmd = cmd.replace("earnapp ", f"{earnapp_path} ", 1)
                elif cmd.strip() == "earnapp":
                    cmd = earnapp_path
            else:
                return "❌ EarnApp tidak ditemukan di sistem. Pastikan EarnApp sudah terinstall dan ada di PATH."
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
    """Jalankan command ADB via wireless"""
    try:
        # Connect ke device ADB via wireless (jika belum connected)
        connect_cmd = f"adb connect {host}:{port}"
        connect_result = subprocess.run(connect_cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        
        # Jika cmd sudah mengandung "shell", langsung gunakan, jika tidak tambahkan "shell"
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

def run_cmd_device(chat_id, cmd):
    dev_name = user_device.get(chat_id)
    if not dev_name:
        return "❌ Device belum dipilih. Gunakan /start untuk memilih device."
    if dev_name not in devices:
        return f"❌ Device '{dev_name}' tidak ditemukan."

    dev = devices[dev_name]
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

def run_cmd_device_by_name(device_name, cmd):
    """Jalankan command di device tertentu berdasarkan nama"""
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
    """Cek status EarnApp via SSH (return simple status)"""
    if device_name not in devices:
        return None
    
    dev = devices[device_name]
    if dev.get("type") not in ["ssh", "local"]:
        return None
    
    try:
        # Prioritas: gunakan output dari earnapp status command
        status_cmd = "earnapp status"
        status_result = run_cmd_device_by_name(device_name, status_cmd)
        
        if status_result and "error" not in status_result.lower():
            # Parse output earnapp status
            status_lower = status_result.lower()
            
            # Cek status: enabled/disabled/running/stopped
            if "status: enabled" in status_lower or "status: running" in status_lower or "enabled" in status_lower:
                return "🟢 Running"
            elif "status: disabled" in status_lower or "status: stopped" in status_lower or "disabled" in status_lower:
                return "🔴 Stopped"
            elif "checking" in status_lower or "- checking status" in status_lower:
                # Jika masih checking, gunakan fallback method
                pass
            elif "running" in status_lower and "not" not in status_lower:
                return "🟢 Running"
            elif "stopped" in status_lower or "stop" in status_lower:
                return "🔴 Stopped"
        
        # Fallback: cek process earnapp jika status command tidak jelas
        cmd = "pgrep -f earnapp || ps aux | grep -i earnapp | grep -v grep"
        result = run_cmd_device_by_name(device_name, cmd)
        
        if result and result.strip() and "error" not in result.lower():
            # Jika ada process, cek lagi dengan earnapp status
            # Tapi jangan langsung return Running, karena bisa jadi process masih ada tapi disabled
            status_cmd2 = "earnapp status 2>&1"
            status_result2 = run_cmd_device_by_name(device_name, status_cmd2)
            if status_result2:
                status_lower2 = status_result2.lower()
                if "disabled" in status_lower2:
                    return "🔴 Stopped"
                elif "enabled" in status_lower2 or "running" in status_lower2:
                    return "🟢 Running"
        
        # Jika tidak ada process, cek apakah earnapp terinstall
        check_cmd = "which earnapp || command -v earnapp"
        check_result = run_cmd_device_by_name(device_name, check_cmd)
        
        if check_result and "earnapp" in check_result and "error" not in check_result.lower():
            return "🔴 Stopped"
        else:
            return "❌ Not installed"
    except Exception as e:
        return f"❌ Error: {str(e)[:50]}"

def get_adb_app_status(device_name):
    """Cek status EarnApp via ADB (return simple status)"""
    if device_name not in devices:
        return "❌ Device tidak ditemukan"
    
    dev = devices[device_name]
    if dev.get("type") != "adb":
        return None
    
    try:
        # Cek apakah app running
        cmd = f"pidof {EARN_APP_PACKAGE}"
        result = run_cmd_device_by_name(device_name, cmd)
        
        if result and result.strip() and not "error" in result.lower() and result.strip().isdigit():
            return "🟢 Running"
        else:
            # Cek apakah app terinstall
            check_cmd = f"pm list packages | grep {EARN_APP_PACKAGE}"
            check_result = run_cmd_device_by_name(device_name, check_cmd)
            if EARN_APP_PACKAGE in check_result:
                return "🔴 Stopped"
            else:
                return "❌ Not installed"
    except Exception as e:
        return f"❌ Error: {str(e)[:50]}"

def format_adb_result(action, result, device_name):
    """Format hasil ADB command menjadi pesan yang lebih simple"""
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
    
    # Jika ada output, cek apakah sukses
    result_lower = result.lower()
    if "error" in result_lower or "failed" in result_lower or "❌" in result:
        return f"❌ Error: {result[:200]}"
    elif "starting" in result_lower or "started" in result_lower:
        status = get_adb_app_status(device_name)
        return f"✅ EarnApp berhasil dijalankan\n\nStatus: {status}"
    else:
        # Output terlalu verbose, ambil status saja
        status = get_adb_app_status(device_name)
        if action == "start":
            return f"✅ EarnApp berhasil dijalankan\n\nStatus: {status}"
        elif action == "stop":
            return f"✅ EarnApp berhasil dihentikan\n\nStatus: {status}"
        else:
            return f"✅ Command berhasil\n\nStatus: {status}"

def start_earnapp_device(device_name):
    """Start EarnApp di device tertentu (otomatis deteksi tipe)"""
    if device_name not in devices:
        return f"❌ Device '{device_name}' tidak ditemukan."
    
    dev = devices[device_name]
    if dev.get("type") == "adb":
        # ADB command: shell am start -n package/activity
        cmd = f"am start -n {EARN_APP_ACTIVITY}"
        result = run_cmd_device_by_name(device_name, cmd)
        return format_adb_result("start", result, device_name)
    else:
        return run_cmd_device_by_name(device_name, "earnapp start")

def stop_earnapp_device(device_name):
    """Stop EarnApp di device tertentu (otomatis deteksi tipe)"""
    if device_name not in devices:
        return f"❌ Device '{device_name}' tidak ditemukan."
    
    dev = devices[device_name]
    if dev.get("type") == "adb":
        # ADB command: shell am force-stop package
        cmd = f"am force-stop {EARN_APP_PACKAGE}"
        result = run_cmd_device_by_name(device_name, cmd)
        return format_adb_result("stop", result, device_name)
    else:
        return run_cmd_device_by_name(device_name, "earnapp stop")

def check_device_health(device_name):
    """Cek kesehatan device"""
    try:
        dev = devices.get(device_name)
        if not dev:
            return False
        
        # Test koneksi dengan command sederhana
        if dev.get("type") == "adb":
            # Untuk ADB, test dengan command yang lebih sederhana
            result = run_cmd_device_by_name(device_name, "getprop ro.build.version.release")
        else:
            # Untuk SSH/local, gunakan echo
            result = run_cmd_device_by_name(device_name, "echo 'health_check'")
        
        # Cek apakah ada error atau hasil kosong
        if result and "error" not in result.lower() and result.strip():
            device_health[device_name] = {
                "status": "online",
                "last_check": int(time.time()),
                "error": None
            }
            return True
        else:
            device_health[device_name] = {
                "status": "offline",
                "last_check": int(time.time()),
                "error": "Command failed or no response"
            }
            return False
    except Exception as e:
        device_health[device_name] = {
            "status": "offline",
            "last_check": int(time.time()),
            "error": str(e)
        }
        return False

def get_dashboard_data():
    """Kumpulkan data untuk dashboard"""
    dashboard_data = []
    
    for device_name in devices.keys():
        dev = devices[device_name]
        
        # Cek kesehatan device
        is_healthy = check_device_health(device_name)
        status_icon = "🟢" if is_healthy else "🔴"
        
        # Dapatkan status EarnApp berdasarkan tipe device
        if dev.get("type") == "adb":
            # Untuk ADB, gunakan status yang lebih simple
            earnapp_status = get_adb_app_status(device_name)
            if earnapp_status and "Running" in earnapp_status:
                earnapp_icon = "🟢"
                status_text = "EarnApp: Running"
            elif earnapp_status and "Stopped" in earnapp_status:
                earnapp_icon = "🔴"
                status_text = "EarnApp: Stopped"
            elif earnapp_status and "Not installed" in earnapp_status:
                earnapp_icon = "❌"
                status_text = "EarnApp: Not installed"
            else:
                earnapp_icon = "⚠️"
                status_text = f"EarnApp: {earnapp_status or 'Unknown'}"
        else:
            # Untuk SSH/local, gunakan helper function yang lebih reliable
            try:
                ssh_status = get_ssh_earnapp_status(device_name)
                
                if ssh_status:
                    if "Running" in ssh_status:
                        earnapp_icon = "🟢"
                        status_text = "EarnApp: Running"
                    elif "Stopped" in ssh_status:
                        earnapp_icon = "🔴"
                        status_text = "EarnApp: Stopped"
                    elif "Not installed" in ssh_status:
                        earnapp_icon = "❌"
                        status_text = "EarnApp: Not installed"
                    else:
                        earnapp_icon = "⚠️"
                        status_text = f"EarnApp: {ssh_status}"
                else:
                    # Fallback: parse langsung dari earnapp status command
                    earnapp_status = run_cmd_device_by_name(device_name, "earnapp status")
                    
                    # Parse output untuk mencari status: disabled/enabled
                    if earnapp_status:
                        status_lower = earnapp_status.lower()
                        if "status: disabled" in status_lower or "disabled" in status_lower:
                            earnapp_icon = "🔴"
                            status_text = "EarnApp: Stopped"
                        elif "status: enabled" in status_lower or ("enabled" in status_lower and "disabled" not in status_lower):
                            earnapp_icon = "🟢"
                            status_text = "EarnApp: Running"
                        elif "- Checking status." in earnapp_status or "checking" in status_lower:
                            earnapp_icon = "🟡"
                            status_text = "EarnApp: Checking..."
                        elif "error" in status_lower or "❌" in earnapp_status:
                            earnapp_icon = "❌"
                            status_text = "EarnApp: Error"
                        elif "running" in status_lower:
                            earnapp_icon = "🟢"
                            status_text = "EarnApp: Running"
                        else:
                            earnapp_icon = "🟡"
                            status_text = "EarnApp: Unknown"
                    else:
                        earnapp_icon = "⚠️"
                        status_text = "EarnApp: Status tidak tersedia"
            except Exception as e:
                earnapp_icon = "❌"
                status_text = f"EarnApp: Error - {str(e)[:50]}"
        
        dashboard_data.append({
            "name": device_name,
            "health": status_icon,
            "earnapp": earnapp_icon,
            "status": status_text
        })
    
    return dashboard_data

def send_alert(chat_id, message):
    """Kirim alert ke admin"""
    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🚨 *ALERT*\n\n{message}", parse_mode="Markdown")
        except Exception as e:
            print(f"Error sending alert: {e}")

def log_activity(device_name, action, result, log_type="manual", user="admin"):
    """Log aktivitas ke activity log"""
    try:
        log_entry = {
            "timestamp": int(time.time()),
            "device": device_name,
            "action": action,  # start/stop/restart
            "result": result[:500] if result else "",  # Limit result length
            "type": log_type,  # manual/auto/scheduled
            "user": user
        }
        
        activity_logs.append(log_entry)
        
        # Keep only last MAX_LOG_ENTRIES
        if len(activity_logs) > MAX_LOG_ENTRIES:
            activity_logs[:] = activity_logs[-MAX_LOG_ENTRIES:]
        
        # Simpan ke file (async, jangan block)
        try:
            with open(ACTIVITY_LOG_FILE, "w") as f:
                json.dump(activity_logs, f, indent=2)
        except Exception as e:
            print(f"Error saving activity log: {e}")
    except Exception as e:
        print(f"Error logging activity: {e}")

def check_alerts():
    """Cek dan kirim alert jika diperlukan"""
    if not alert_settings["enabled"]:
        return
    
    current_time = int(time.time())
    
    for device_name, health_info in device_health.items():
        if health_info["status"] == "offline":
            time_diff = current_time - health_info["last_check"]
            if time_diff > alert_settings["offline_threshold"]:
                send_alert(ADMIN_ID, f"Device '{device_name}' offline selama {time_diff//60} menit")

# -----------------------
# Menu Telegram
# -----------------------
def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🟢 Start EarnApp"),
        types.KeyboardButton("🔴 Stop EarnApp"),
        types.KeyboardButton("🟡 Status"),
        types.KeyboardButton("📊 Status All")
    )
    markup.add(
        types.KeyboardButton("🆔 Show ID"),
        types.KeyboardButton("💣 Uninstall"),
        types.KeyboardButton("🔄 Ganti Device"),
        types.KeyboardButton("➕ Add Device")
    )
    markup.add(
        types.KeyboardButton("🚀 Start All"),
        types.KeyboardButton("🛑 Stop All"),
        types.KeyboardButton("🔍 Health Check"),
        types.KeyboardButton("⏰ Schedule")
    )
    markup.add(
        types.KeyboardButton("⚡ Quick Actions"),
        types.KeyboardButton("📝 Activity Log"),
        types.KeyboardButton("🗑️ Remove Device")
    )
    markup.add(
        types.KeyboardButton("🗑️ Uninstall Bot")
    )
    markup.add(
        types.KeyboardButton("🔄 Restart Bot")
    )
    bot.send_message(chat_id, "Silakan pilih menu di bawah ini 👇", reply_markup=markup)

def show_device_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for name in devices.keys():
        markup.add(types.KeyboardButton(name))
    bot.send_message(chat_id, "Pilih device yang ingin dikontrol:", reply_markup=markup)

# -----------------------
# Handlers
# -----------------------
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(msg.from_user.id) != str(ADMIN_ID):
        bot.reply_to(msg, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.reply_to(msg, "🤖 Bot EarnApp aktif! Pilih device yang ingin dikontrol.")
    show_device_menu(msg.chat.id)

# Pilih device
@bot.message_handler(func=lambda m: m.text in devices)
def select_device(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    # Jika sedang dalam flow remove device
    if m.chat.id in remove_device_state:
        device_name = m.text
        if device_name not in devices:
            bot.send_message(m.chat.id, f"❌ Device '{device_name}' tidak ditemukan.")
            remove_device_state.pop(m.chat.id, None)
            show_main_menu(m.chat.id)
            return

        # Konfirmasi penghapusan
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"confirm_remove:{device_name}"),
            types.InlineKeyboardButton("❌ Batal", callback_data="cancel_remove")
        )
        bot.send_message(m.chat.id, f"⚠️ *Konfirmasi Hapus Device*\n\nApakah Anda yakin ingin menghapus device '*{device_name}*'?\n\n**Peringatan:** Tindakan ini akan menghapus device dari konfigurasi.", parse_mode="Markdown", reply_markup=markup)
        return

    # Normal select device (pilih untuk kontrol)
    user_device[m.chat.id] = m.text
    bot.send_message(m.chat.id, f"✅ Device '{m.text}' dipilih.")
    show_main_menu(m.chat.id)

# Tambah device via Telegram
@bot.message_handler(commands=['adddevice'])
@bot.message_handler(func=lambda m: m.text == "➕ Add Device")
def add_device_start(msg):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(msg.from_user.id) != str(ADMIN_ID):
        bot.reply_to(msg, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    chat_id = msg.chat.id
    add_device_state[chat_id] = {"step": 0, "data": {}}
    
    # Tampilkan pilihan tipe device
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔌 SSH Device", callback_data="add_device_type:ssh"),
        types.InlineKeyboardButton("📱 ADB Device (Wireless)", callback_data="add_device_type:adb")
    )
    bot.send_message(chat_id, "📱 *TAMBAH DEVICE BARU*\n\nPilih tipe device yang ingin ditambahkan:", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("add_device_type:"))
def add_device_type_callback(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    device_type = call.data.split(":")[1]
    chat_id = call.message.chat.id
    
    if chat_id not in add_device_state:
        add_device_state[chat_id] = {"step": 0, "data": {}}
    
    add_device_state[chat_id]["data"]["device_type"] = device_type
    add_device_state[chat_id]["step"] = 1
    
    bot.answer_callback_query(call.id, f"✅ Tipe device: {device_type.upper()}")
    bot.edit_message_text(
        f"📱 *TAMBAH DEVICE BARU*\n\nTipe: **{device_type.upper()}**\n\nMasukkan IP address device:",
        chat_id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.chat.id in add_device_state)
def add_device_process(msg):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(msg.from_user.id) != str(ADMIN_ID):
        bot.reply_to(msg, "❌ Anda tidak memiliki akses ke bot ini.")
        add_device_state.pop(msg.chat.id, None)
        return
        
    chat_id = msg.chat.id
    state = add_device_state[chat_id]
    step = state["step"]
    device_type = state["data"].get("device_type", "ssh")

    if step == 0:
        # Skip - handled by callback
        return
    elif step == 1:
        state["data"]["host"] = msg.text
        state["step"] = 2
        bot.send_message(chat_id, "Masukkan nama device:")
    elif step == 2:
        state["data"]["name"] = msg.text
        if device_type == "adb":
            # Untuk ADB, langsung minta port (default 5555)
            state["step"] = 3
            bot.send_message(chat_id, "Masukkan port ADB (default: 5555, tekan Enter untuk default):")
        else:
            # Untuk SSH, minta username
            state["step"] = 3
            bot.send_message(chat_id, "Masukkan username SSH:")
    elif step == 3:
        if device_type == "adb":
            # Port ADB
            port_text = msg.text.strip()
            if not port_text:
                port = 5555
            else:
                try:
                    port = int(port_text)
                except ValueError:
                    bot.send_message(chat_id, "❌ Port tidak valid. Masukkan angka atau tekan Enter untuk default (5555):")
                    return
            
            # Simpan device ADB
            data = state["data"]
            devices[data["name"]] = {
                "type": "adb",
                "host": data["host"],
                "port": port
            }
            # simpan ke file JSON
            with open(DEVICE_FILE, "w") as f:
                json.dump(devices, f, indent=2)
            bot.send_message(chat_id, f"✅ Device ADB '{data['name']}' berhasil ditambahkan!\n\nIP: {data['host']}\nPort: {port}")
            add_device_state.pop(chat_id)
            show_main_menu(chat_id)
        else:
            # Username SSH
            state["data"]["user"] = msg.text
            state["step"] = 4
            bot.send_message(chat_id, "Masukkan password SSH:")
    elif step == 4:
        # Password SSH (hanya untuk SSH)
        state["data"]["password"] = msg.text
        data = state["data"]
        devices[data["name"]] = {
            "type": "ssh",
            "host": data["host"],
            "port": 22,
            "user": data["user"],
            "password": data["password"]
        }
        # simpan ke file JSON
        with open(DEVICE_FILE, "w") as f:
            json.dump(devices, f, indent=2)
        bot.send_message(chat_id, f"✅ Device SSH '{data['name']}' berhasil ditambahkan!")
        add_device_state.pop(chat_id)
        show_main_menu(chat_id)

# Menu kontrol
@bot.message_handler(func=lambda m: m.text == "🟡 Status")
def handler_status(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    device_name = user_device.get(m.chat.id, "—")
    if device_name not in devices:
        bot.reply_to(m, f"❌ Device '{device_name}' tidak ditemukan.")
        return
    
    dev = devices[device_name]
    
    # Cek tipe device dan jalankan command sesuai
    if dev.get("type") == "adb":
        # Gunakan helper function untuk status yang lebih simple
        status = get_adb_app_status(device_name)
        if status:
            out = f"Package: {EARN_APP_PACKAGE}\nStatus: {status}"
        else:
            out = f"Package: {EARN_APP_PACKAGE}\nStatus: Unknown"
    else:
        # Gunakan command earnapp untuk SSH/local
        out = run_cmd_device(m.chat.id, "earnapp status")
    
    bot.reply_to(m, f"📊 *Status ({device_name}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🟢 Start EarnApp")
def handler_start(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    device_name = user_device.get(m.chat.id, "—")
    if device_name not in devices:
        bot.reply_to(m, f"❌ Device '{device_name}' tidak ditemukan.")
        return
    
    dev = devices[device_name]
    
    # Cek tipe device dan jalankan command sesuai
    if dev.get("type") == "adb":
        # Gunakan helper function yang sudah format output
        status_out = start_earnapp_device(device_name)
    else:
        # Gunakan command earnapp untuk SSH/local
        run_cmd_device(m.chat.id, "earnapp start")
        out = run_cmd_device(m.chat.id, "earnapp status")
        status_out = out
    
    # Log activity
    log_activity(device_name, "start", status_out, "manual", str(m.from_user.id))
    
    # Kirim notifikasi ke admin
    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🟢 *MANUAL START*\n\n"
                f"Device: **{device_name}**\n"
                f"User: {m.from_user.first_name} (@{m.from_user.username or 'N/A'})\n\n"
                f"**Result:**\n```\n{status_out}\n```",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error sending notification: {e}")
    
    bot.reply_to(m, f"🟢 *Menjalankan EarnApp ({device_name}):*\n```\n{status_out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔴 Stop EarnApp")
def handler_stop(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    device_name = user_device.get(m.chat.id, "—")
    if device_name not in devices:
        bot.reply_to(m, f"❌ Device '{device_name}' tidak ditemukan.")
        return
    
    dev = devices[device_name]
    
    # Cek tipe device dan jalankan command sesuai
    if dev.get("type") == "adb":
        # Gunakan helper function yang sudah format output
        status_out = stop_earnapp_device(device_name)
    else:
        # Gunakan command earnapp untuk SSH/local
        run_cmd_device(m.chat.id, "earnapp stop")
        out = run_cmd_device(m.chat.id, "earnapp status")
        status_out = out
    
    # Log activity
    log_activity(device_name, "stop", status_out, "manual", str(m.from_user.id))
    
    # Kirim notifikasi ke admin
    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🔴 *MANUAL STOP*\n\n"
                f"Device: **{device_name}**\n"
                f"User: {m.from_user.first_name} (@{m.from_user.username or 'N/A'})\n\n"
                f"**Result:**\n```\n{status_out}\n```",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error sending notification: {e}")
    
    bot.reply_to(m, f"🔴 *Menghentikan EarnApp ({device_name}):*\n```\n{status_out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🆔 Show ID")
def handler_showid(m):
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return

    dev_name = user_device.get(m.chat.id)
    if not dev_name:
        bot.reply_to(m, "❌ Device belum dipilih.")
        return

    out = run_cmd_device(m.chat.id, "earnapp showid")
    bot.reply_to(m, f"🆔 *Device ID ({dev_name}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💣 Uninstall")
def handler_uninstall(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    # Konfirmasi uninstall
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ya, Uninstall", callback_data="confirm_uninstall"),
        types.InlineKeyboardButton("❌ Batal", callback_data="cancel_uninstall")
    )
    bot.reply_to(m, "⚠️ *Konfirmasi Uninstall EarnApp*\n\nApakah Anda yakin ingin menghapus EarnApp dari device ini?\n\n**Peringatan:** Tindakan ini tidak dapat dibatalkan!", 
                 parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_uninstall")
def confirm_uninstall(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "🔄 Memproses uninstall...")
    
    # Jalankan uninstall
    out = run_cmd_device(call.message.chat.id, "earnapp uninstall")
    
    # Edit pesan dengan hasil
    bot.edit_message_text(
        f"💣 *Uninstall EarnApp ({user_device.get(call.message.chat.id, '—')}):*\n```\n{out}\n```\n\n✅ Uninstall selesai!",
        call.message.chat.id, 
        call.message.message_id, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_uninstall")
def cancel_uninstall(call):
    bot.answer_callback_query(call.id, "❌ Uninstall dibatalkan")
    bot.edit_message_text(
        "❌ Uninstall dibatalkan.\n\nGunakan menu lain untuk mengontrol EarnApp.",
        call.message.chat.id, 
        call.message.message_id
    )

@bot.message_handler(func=lambda m: m.text == "🔄 Ganti Device")
def handler_change_device(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    show_device_menu(m.chat.id)

# Status All Devices
@bot.message_handler(func=lambda m: m.text == "📊 Status All")
def handler_status_all(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.reply_to(m, "🔄 Mengumpulkan status semua device...")
    
    # Kumpulkan data dashboard
    dashboard_data = get_dashboard_data()
    
    # Format pesan status all
    message = "📊 *STATUS ALL DEVICES*\n\n"
    
    for device in dashboard_data:
        message += f"{device['health']} {device['earnapp']} *{device['name']}*\n"
        message += f"```\n{device['status']}\n```\n\n"
    
    if not dashboard_data:
        message += "❌ Tidak ada device yang dikonfigurasi."
    
    bot.reply_to(m, message, parse_mode="Markdown")

# Bulk Operations - Start All
@bot.message_handler(func=lambda m: m.text == "🚀 Start All")
def handler_start_all(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.reply_to(m, "🚀 Memulai EarnApp di semua device...")
    
    results = []
    for device_name in devices.keys():
        result = start_earnapp_device(device_name)
        results.append(f"**{device_name}**: {result}")
        
        # Log activity
        log_activity(device_name, "start", result, "manual", str(m.from_user.id))
    
    message = "🚀 *START ALL DEVICES*\n\n" + "\n".join(results)
    bot.reply_to(m, message, parse_mode="Markdown")
    
    # Kirim notifikasi ke admin
    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🚀 *START ALL DEVICES*\n\n"
                f"User: {m.from_user.first_name} (@{m.from_user.username or 'N/A'})\n"
                f"Total devices: {len(devices)}\n\n"
                f"**Results:**\n" + "\n".join(results),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error sending notification: {e}")

# Bulk Operations - Stop All
@bot.message_handler(func=lambda m: m.text == "🛑 Stop All")
def handler_stop_all(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    # Konfirmasi stop all
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ya, Stop All", callback_data="confirm_stop_all"),
        types.InlineKeyboardButton("❌ Batal", callback_data="cancel_stop_all")
    )
    bot.reply_to(m, "⚠️ *Konfirmasi Stop All*\n\nApakah Anda yakin ingin menghentikan EarnApp di semua device?", 
                 parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_stop_all")
def confirm_stop_all(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "🛑 Menghentikan semua device...")
    
    results = []
    for device_name in devices.keys():
        result = stop_earnapp_device(device_name)
        results.append(f"**{device_name}**: {result}")
        
        # Log activity
        log_activity(device_name, "stop", result, "manual", str(call.from_user.id))
    
    message = "🛑 *STOP ALL DEVICES*\n\n" + "\n".join(results)
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    # Kirim notifikasi ke admin
    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🛑 *STOP ALL DEVICES*\n\n"
                f"User: {call.from_user.first_name} (@{call.from_user.username or 'N/A'})\n"
                f"Total devices: {len(devices)}\n\n"
                f"**Results:**\n" + "\n".join(results),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error sending notification: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_stop_all")
def cancel_stop_all(call):
    bot.answer_callback_query(call.id, "❌ Stop all dibatalkan")
    bot.edit_message_text("❌ Stop all dibatalkan.", call.message.chat.id, call.message.message_id)


# Callback: konfirmasi hapus device
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("confirm_remove:"))
def confirm_remove_device(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return

    device_name = call.data.split(":", 1)[1]
    if device_name not in devices:
        bot.answer_callback_query(call.id, f"❌ Device '{device_name}' tidak ditemukan.")
        try:
            bot.edit_message_text(f"❌ Device '{device_name}' tidak ditemukan.", call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        remove_device_state.pop(call.message.chat.id, None)
        return

    # Hapus device dari konfigurasi
    try:
        del devices[device_name]
        with open(DEVICE_FILE, "w") as f:
            json.dump(devices, f, indent=2)
        try:
            os.chmod(DEVICE_FILE, 0o600)
        except Exception:
            pass

        # Hapus referensi di user_device
        to_remove = [k for k, v in user_device.items() if v == device_name]
        for k in to_remove:
            user_device.pop(k, None)

        bot.answer_callback_query(call.id, "✅ Device dihapus")
        bot.edit_message_text(f"✅ Device '*{device_name}*' berhasil dihapus dari konfigurasi.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Gagal menghapus device")
        bot.edit_message_text(f"❌ Gagal menghapus device '{device_name}': {e}", call.message.chat.id, call.message.message_id)

    remove_device_state.pop(call.message.chat.id, None)


@bot.callback_query_handler(func=lambda call: call.data == "cancel_remove")
def cancel_remove(call):
    bot.answer_callback_query(call.id, "❌ Hapus device dibatalkan")
    try:
        bot.edit_message_text("❌ Hapus device dibatalkan.", call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    remove_device_state.pop(call.message.chat.id, None)

# Health Check
@bot.message_handler(func=lambda m: m.text == "🔍 Health Check")
def handler_health_check(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.reply_to(m, "🔍 Melakukan health check semua device...")
    
    results = []
    for device_name in devices.keys():
        is_healthy = check_device_health(device_name)
        health_info = device_health.get(device_name, {})
        
        status_icon = "🟢" if is_healthy else "🔴"
        error_msg = f" - {health_info.get('error', 'Unknown error')}" if not is_healthy else ""
        
        results.append(f"{status_icon} **{device_name}**: {'Online' if is_healthy else 'Offline'}{error_msg}")
    
    message = "🔍 *HEALTH CHECK RESULTS*\n\n" + "\n".join(results)
    bot.reply_to(m, message, parse_mode="Markdown")


# Mulai flow hapus device
@bot.message_handler(func=lambda m: m.text == "🗑️ Remove Device")
def handler_remove_device(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return

    chat_id = m.chat.id
    remove_device_state[chat_id] = True
    bot.send_message(chat_id, "Pilih device yang ingin dihapus:")
    show_device_menu(chat_id)

# Quick Actions
@bot.message_handler(func=lambda m: m.text == "⚡ Quick Actions")
def handler_quick_actions(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    # Tampilkan menu quick actions
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Quick Restart", callback_data="quick_restart"),
        types.InlineKeyboardButton("📊 Quick Status", callback_data="quick_status")
    )
    markup.add(
        types.InlineKeyboardButton("✅ Enable Auto Restart All", callback_data="enable_auto_restart_all"),
        types.InlineKeyboardButton("❌ Disable Auto Restart All", callback_data="disable_auto_restart_all")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")
    )
    
    bot.reply_to(m, "⚡ *QUICK ACTIONS*\n\nPilih aksi cepat di bawah ini:", 
                 parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "quick_restart")
def quick_restart(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "🔄 Quick Restart...")
    
    # Tampilkan pilihan device
    if not devices:
        bot.edit_message_text(
            "❌ Tidak ada device yang dikonfigurasi.",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    markup = types.InlineKeyboardMarkup()
    for device_name in devices.keys():
        markup.add(types.InlineKeyboardButton(device_name, callback_data=f"quick_restart_device:{device_name}"))
    markup.add(types.InlineKeyboardButton("🔄 Restart All", callback_data="quick_restart_all"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_quick_actions"))
    
    bot.edit_message_text(
        "🔄 *QUICK RESTART*\n\nPilih device yang ingin di-restart (stop → wait 5s → start):",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("quick_restart_device:"))
def quick_restart_device(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    device_name = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id, f"🔄 Restarting {device_name}...")
    
    bot.edit_message_text(
        f"🔄 *QUICK RESTART*\n\nDevice: **{device_name}**\n\n⏳ Memproses restart...",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )
    
    # Jalankan stop → wait → start
    stop_result = stop_earnapp_device(device_name)
    time.sleep(5)
    start_result = start_earnapp_device(device_name)
    
    # Log activity
    log_activity(device_name, "restart", f"Stop: {stop_result[:200]}\nStart: {start_result[:200]}", "manual", str(call.from_user.id))
    
    # Kirim notifikasi ke admin
    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🔄 *QUICK RESTART*\n\n"
                f"Device: **{device_name}**\n"
                f"User: {call.from_user.first_name} (@{call.from_user.username or 'N/A'})\n\n"
                f"**Stop Result:**\n```\n{stop_result}\n```\n\n"
                f"**Start Result:**\n```\n{start_result}\n```",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error sending notification: {e}")
    
    bot.edit_message_text(
        f"✅ *QUICK RESTART SELESAI*\n\nDevice: **{device_name}**\n\n"
        f"**Stop Result:**\n```\n{stop_result}\n```\n\n"
        f"**Start Result:**\n```\n{start_result}\n```",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "quick_restart_all")
def quick_restart_all(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "🔄 Restarting all devices...")
    
    bot.edit_message_text(
        "🔄 *QUICK RESTART ALL*\n\n⏳ Memproses restart semua device...",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )
    
    results = []
    for device_name in devices.keys():
        stop_result = stop_earnapp_device(device_name)
        time.sleep(5)
        start_result = start_earnapp_device(device_name)
        results.append(f"**{device_name}**\nStop: {stop_result[:50]}...\nStart: {start_result[:50]}...")
    
    message = "✅ *QUICK RESTART ALL SELESAI*\n\n" + "\n\n".join(results)
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    # Kirim notifikasi ke admin
    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🔄 *QUICK RESTART ALL*\n\n"
                f"User: {call.from_user.first_name} (@{call.from_user.username or 'N/A'})\n"
                f"Total devices: {len(devices)}\n\n"
                f"**Results:**\n" + "\n\n".join(results),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error sending notification: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "quick_status")
def quick_status(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "📊 Checking status...")
    
    bot.edit_message_text(
        "📊 *QUICK STATUS*\n\n⏳ Mengumpulkan status semua device...",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )
    
    results = []
    for device_name in devices.keys():
        status = run_cmd_device_by_name(device_name, "earnapp status")
        is_running = "running" in status.lower()
        icon = "🟢" if is_running else "🔴"
        results.append(f"{icon} **{device_name}**: {'Running' if is_running else 'Stopped'}\n```\n{status[:100]}\n```")
    
    message = "📊 *QUICK STATUS ALL DEVICES*\n\n" + "\n\n".join(results)
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "enable_auto_restart_all")
def enable_auto_restart_all(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "✅ Enabling auto restart all...")
    
    enabled_count = 0
    for device_name in devices.keys():
        if device_name not in auto_restart_settings:
            # Buat default settings jika belum ada
            auto_restart_settings[device_name] = {
                "enabled": True,
                "interval_hours": 6,
                "delay_seconds": 5,
                "last_run": int(time.time())
            }
            enabled_count += 1
        elif not auto_restart_settings[device_name].get("enabled", False):
            auto_restart_settings[device_name]["enabled"] = True
            enabled_count += 1
    
    # Simpan ke file
    with open(AUTO_RESTART_FILE, "w") as f:
        json.dump(auto_restart_settings, f, indent=2)
    
    bot.edit_message_text(
        f"✅ *ENABLE AUTO RESTART ALL*\n\nBerhasil mengaktifkan auto restart untuk {enabled_count} device.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "disable_auto_restart_all")
def disable_auto_restart_all(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "❌ Disabling auto restart all...")
    
    disabled_count = 0
    for device_name in devices.keys():
        if device_name in auto_restart_settings and auto_restart_settings[device_name].get("enabled", False):
            auto_restart_settings[device_name]["enabled"] = False
            disabled_count += 1
    
    # Simpan ke file
    with open(AUTO_RESTART_FILE, "w") as f:
        json.dump(auto_restart_settings, f, indent=2)
    
    bot.edit_message_text(
        f"❌ *DISABLE AUTO RESTART ALL*\n\nBerhasil menonaktifkan auto restart untuk {disabled_count} device.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_quick_actions")
def back_to_quick_actions(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "🔙 Kembali")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Quick Restart", callback_data="quick_restart"),
        types.InlineKeyboardButton("📊 Quick Status", callback_data="quick_status")
    )
    markup.add(
        types.InlineKeyboardButton("✅ Enable Auto Restart All", callback_data="enable_auto_restart_all"),
        types.InlineKeyboardButton("❌ Disable Auto Restart All", callback_data="disable_auto_restart_all")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")
    )
    
    bot.edit_message_text(
        "⚡ *QUICK ACTIONS*\n\nPilih aksi cepat di bawah ini:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    bot.answer_callback_query(call.id, "🔙 Kembali ke menu utama")
    show_main_menu(call.message.chat.id)

# Schedule Tasks
@bot.message_handler(func=lambda m: m.text == "⏰ Schedule")
def handler_schedule(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    # Tampilkan menu schedule
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Auto Restart", callback_data="auto_restart_menu"),
        types.InlineKeyboardButton("🕐 Time Schedule", callback_data="time_schedule_menu")
    )
    markup.add(
        types.InlineKeyboardButton("📋 List Schedule", callback_data="list_schedule"),
        types.InlineKeyboardButton("⚙️ Settings", callback_data="schedule_settings")
    )
    
    bot.reply_to(m, "⏰ *SCHEDULED TASKS*\n\nPilih opsi di bawah ini:", 
                 parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🗑️ Uninstall Bot")
def handler_uninstall_bot_button(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    # Konfirmasi uninstall bot
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ya, Hapus Bot", callback_data="confirm_uninstall_bot"),
        types.InlineKeyboardButton("❌ Batal", callback_data="cancel_uninstall_bot")
    )
    bot.reply_to(m, "⚠️ *Konfirmasi Uninstall Bot*\n\nApakah Anda yakin ingin menghapus bot ini dari server?\n\n**Peringatan:** Bot akan berhenti dan semua data akan dihapus!", 
                 parse_mode="Markdown", reply_markup=markup)

# Command untuk uninstall bot
@bot.message_handler(commands=['uninstallbot'])
def handler_uninstall_bot(msg):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(msg.from_user.id) != str(ADMIN_ID):
        bot.reply_to(msg, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    # Konfirmasi uninstall bot
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ya, Hapus Bot", callback_data="confirm_uninstall_bot"),
        types.InlineKeyboardButton("❌ Batal", callback_data="cancel_uninstall_bot")
    )
    bot.reply_to(msg, "⚠️ *Konfirmasi Uninstall Bot*\n\nApakah Anda yakin ingin menghapus bot ini dari server?\n\n**Peringatan:** Bot akan berhenti dan semua data akan dihapus!", 
                 parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_uninstall_bot")
def confirm_uninstall_bot(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "🔄 Memproses uninstall bot...")
    
    # Kirim pesan terakhir
    bot.edit_message_text(
        "🔄 *Uninstall Bot*\n\nBot sedang dihentikan dan dihapus dari server...\n\n👋 Terima kasih telah menggunakan EarnApp Bot!",
        call.message.chat.id, 
        call.message.message_id, 
        parse_mode="Markdown"
    )
    
    # Jalankan script uninstall
    try:
        import subprocess
        subprocess.Popen(['sudo', 'bash', '/srv/earnapp_bot/uninstall.sh'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error running uninstall script: {e}")
    
    # Stop bot
    import sys
    sys.exit(0)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_uninstall_bot")
def cancel_uninstall_bot(call):
    bot.answer_callback_query(call.id, "❌ Uninstall bot dibatalkan")
    bot.edit_message_text(
        "❌ Uninstall bot dibatalkan.\n\nBot tetap aktif dan siap digunakan.",
        call.message.chat.id, 
        call.message.message_id
    )

# Schedule Callback Handlers
@bot.callback_query_handler(func=lambda call: call.data == "auto_restart_menu")
def auto_restart_menu(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "🔄 Menu Auto Restart")
    
    # Tampilkan menu auto restart
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ Set Auto Restart", callback_data="set_auto_restart"),
        types.InlineKeyboardButton("📋 List Auto Restart", callback_data="list_auto_restart")
    )
    markup.add(
        types.InlineKeyboardButton("❌ Disable Auto Restart", callback_data="disable_auto_restart"),
        types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_schedule")
    )
    
    bot.edit_message_text(
        "🔄 *AUTO RESTART*\n\nFitur ini akan otomatis stop dan start EarnApp setiap beberapa jam.\n\nPilih opsi di bawah ini:",
        call.message.chat.id, 
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_schedule")
def back_to_schedule(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "🔙 Kembali")
    
    # Tampilkan menu schedule
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Auto Restart", callback_data="auto_restart_menu"),
        types.InlineKeyboardButton("🕐 Time Schedule", callback_data="time_schedule_menu")
    )
    markup.add(
        types.InlineKeyboardButton("📋 List Schedule", callback_data="list_schedule"),
        types.InlineKeyboardButton("⚙️ Settings", callback_data="schedule_settings")
    )
    
    bot.edit_message_text(
        "⏰ *SCHEDULED TASKS*\n\nPilih opsi di bawah ini:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

# Time-based Schedule Handlers
@bot.callback_query_handler(func=lambda call: call.data == "time_schedule_menu")
def time_schedule_menu(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "🕐 Time Schedule Menu")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ Add Time Schedule", callback_data="add_time_schedule"),
        types.InlineKeyboardButton("📋 List Time Schedule", callback_data="list_time_schedule")
    )
    markup.add(
        types.InlineKeyboardButton("🗑️ Delete Time Schedule", callback_data="delete_time_schedule"),
        types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_schedule")
    )
    
    bot.edit_message_text(
        "🕐 *TIME-BASED SCHEDULE*\n\nJadwalkan start/stop/restart pada waktu tertentu.\n\nPilih opsi di bawah ini:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "add_time_schedule")
def add_time_schedule(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "➕ Add Time Schedule")
    
    if not devices:
        bot.edit_message_text(
            "❌ Tidak ada device yang dikonfigurasi.\n\nTambahkan device terlebih dahulu menggunakan /adddevice",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    # Mulai flow input schedule
    chat_id = call.message.chat.id
    schedule_state[chat_id] = {"step": 1, "data": {}}
    
    markup = types.InlineKeyboardMarkup()
    for device_name in devices.keys():
        markup.add(types.InlineKeyboardButton(device_name, callback_data=f"time_schedule_device:{device_name}"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="time_schedule_menu"))
    
    bot.edit_message_text(
        "🕐 *ADD TIME SCHEDULE*\n\nPilih device:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("time_schedule_device:"))
def time_schedule_device(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    device_name = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    
    if chat_id not in schedule_state:
        schedule_state[chat_id] = {"step": 1, "data": {}}
    
    schedule_state[chat_id]["data"]["device"] = device_name
    schedule_state[chat_id]["step"] = 2
    
    bot.answer_callback_query(call.id, f"Device: {device_name}")
    bot.edit_message_text(
        f"🕐 *ADD TIME SCHEDULE*\n\nDevice: **{device_name}**\n\nPilih action:",
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔄 Restart", callback_data="time_schedule_action:restart"),
            types.InlineKeyboardButton("🟢 Start", callback_data="time_schedule_action:start"),
            types.InlineKeyboardButton("🔴 Stop", callback_data="time_schedule_action:stop")
        ).add(types.InlineKeyboardButton("🔙 Kembali", callback_data="add_time_schedule"))
    )

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("time_schedule_action:"))
def time_schedule_action(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    action = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    
    if chat_id not in schedule_state:
        bot.answer_callback_query(call.id, "❌ Session expired")
        return
    
    schedule_state[chat_id]["data"]["action"] = action
    schedule_state[chat_id]["step"] = 3
    
    bot.answer_callback_query(call.id, f"Action: {action}")
    bot.edit_message_text(
        f"🕐 *ADD TIME SCHEDULE*\n\nDevice: **{schedule_state[chat_id]['data']['device']}**\n"
        f"Action: **{action.upper()}**\n\n"
        f"Masukkan waktu dalam format HH:MM (contoh: 08:00):",
        chat_id,
        call.message.message_id, 
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.chat.id in schedule_state and schedule_state[m.chat.id]["step"] == 3)
def process_time_schedule_time(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        schedule_state.pop(m.chat.id, None)
        return
    
    try:
        # Validasi format waktu HH:MM
        time_str = m.text.strip()
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError("Format tidak valid")
        
        hour = int(parts[0])
        minute = int(parts[1])
        
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Waktu tidak valid")
        
        schedule_state[m.chat.id]["data"]["time"] = time_str
        schedule_state[m.chat.id]["step"] = 4
        
        # Tampilkan pilihan hari
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Setiap Hari", callback_data="time_schedule_days:daily"),
            types.InlineKeyboardButton("Hari Kerja (Sen-Jum)", callback_data="time_schedule_days:weekdays")
        )
        markup.add(
            types.InlineKeyboardButton("Weekend (Sab-Ming)", callback_data="time_schedule_days:weekends"),
            types.InlineKeyboardButton("Pilih Manual", callback_data="time_schedule_days:manual")
        )
        
        bot.reply_to(m, f"🕐 *ADD TIME SCHEDULE*\n\n"
                       f"Device: **{schedule_state[m.chat.id]['data']['device']}**\n"
                       f"Action: **{schedule_state[m.chat.id]['data']['action'].upper()}**\n"
                       f"Waktu: **{time_str}**\n\n"
                       f"Pilih hari:",
                 parse_mode="Markdown", reply_markup=markup)
    except (ValueError, IndexError):
        bot.reply_to(m, "❌ Format waktu tidak valid. Gunakan format HH:MM (contoh: 08:00):")

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("time_schedule_days:"))
def time_schedule_days(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    days_type = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    
    if chat_id not in schedule_state:
        bot.answer_callback_query(call.id, "❌ Session expired")
        return
    
    # Mapping hari: 0=Senin, 1=Selasa, ..., 6=Minggu
    if days_type == "daily":
        days = [0, 1, 2, 3, 4, 5, 6]
    elif days_type == "weekdays":
        days = [0, 1, 2, 3, 4]  # Senin-Jumat
    elif days_type == "weekends":
        days = [5, 6]  # Sabtu-Minggu
    else:  # manual
        schedule_state[chat_id]["step"] = 5
        bot.answer_callback_query(call.id, "Pilih hari manual")
        bot.edit_message_text(
            "🕐 *ADD TIME SCHEDULE*\n\nPilih hari (bisa multiple):\n\n"
            "0=Senin, 1=Selasa, 2=Rabu, 3=Kamis, 4=Jumat, 5=Sabtu, 6=Minggu\n\n"
            "Masukkan angka hari dipisah koma (contoh: 0,1,2,3,4):",
            chat_id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        return
    
    # Simpan schedule
    schedule_state[chat_id]["data"]["days"] = days
    schedule_state[chat_id]["data"]["enabled"] = True
    schedule_state[chat_id]["data"]["timezone"] = "UTC"
    
    # Generate task_id
    task_id = f"{schedule_state[chat_id]['data']['device']}_{schedule_state[chat_id]['data']['time']}_{schedule_state[chat_id]['data']['action']}"
    scheduled_tasks[task_id] = schedule_state[chat_id]["data"].copy()
    
    # Simpan ke file
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(scheduled_tasks, f, indent=2)
    
    # Hapus state
    schedule_state.pop(chat_id, None)
    
    days_str = "Setiap hari" if days_type == "daily" else ("Hari kerja" if days_type == "weekdays" else "Weekend")
    bot.answer_callback_query(call.id, "✅ Schedule ditambahkan")
    bot.edit_message_text(
        f"✅ *TIME SCHEDULE DITAMBAHKAN*\n\n"
        f"Device: **{scheduled_tasks[task_id]['device']}**\n"
        f"Action: **{scheduled_tasks[task_id]['action'].upper()}**\n"
        f"Waktu: **{scheduled_tasks[task_id]['time']}**\n"
        f"Hari: **{days_str}**\n"
        f"Status: ✅ Aktif",
        chat_id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.chat.id in schedule_state and schedule_state[m.chat.id]["step"] == 5)
def process_time_schedule_days_manual(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        schedule_state.pop(m.chat.id, None)
        return
    
    try:
        days_input = m.text.strip()
        days = [int(d.strip()) for d in days_input.split(",")]
        
        # Validasi
        if not all(0 <= d <= 6 for d in days):
            raise ValueError("Hari harus antara 0-6")
        
        schedule_state[m.chat.id]["data"]["days"] = days
        schedule_state[m.chat.id]["data"]["enabled"] = True
        schedule_state[m.chat.id]["data"]["timezone"] = "UTC"
        
        # Generate task_id
        task_id = f"{schedule_state[m.chat.id]['data']['device']}_{schedule_state[m.chat.id]['data']['time']}_{schedule_state[m.chat.id]['data']['action']}"
        scheduled_tasks[task_id] = schedule_state[m.chat.id]["data"].copy()
        
        # Simpan ke file
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(scheduled_tasks, f, indent=2)
        
        # Hapus state
        schedule_state.pop(m.chat.id, None)
        
        days_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        days_str = ", ".join([days_names[d] for d in days])
        
        bot.reply_to(m, f"✅ *TIME SCHEDULE DITAMBAHKAN*\n\n"
                       f"Device: **{scheduled_tasks[task_id]['device']}**\n"
                       f"Action: **{scheduled_tasks[task_id]['action'].upper()}**\n"
                       f"Waktu: **{scheduled_tasks[task_id]['time']}**\n"
                       f"Hari: **{days_str}**\n"
                       f"Status: ✅ Aktif",
                 parse_mode="Markdown")
    except (ValueError, IndexError):
        bot.reply_to(m, "❌ Format tidak valid. Masukkan angka 0-6 dipisah koma (contoh: 0,1,2,3,4):")

@bot.callback_query_handler(func=lambda call: call.data == "list_time_schedule")
def list_time_schedule(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "📋 List Time Schedule")
    
    if not scheduled_tasks:
        message = "🕐 *TIME-BASED SCHEDULES*\n\n❌ Tidak ada schedule yang dikonfigurasi."
    else:
        message = "🕐 *TIME-BASED SCHEDULES*\n\n"
        days_names = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
        
        for task_id, task in scheduled_tasks.items():
            status_icon = "✅" if task.get("enabled", True) else "❌"
            days = task.get("days", [])
            days_str = ", ".join([days_names[d] for d in days]) if days else "Tidak ada"
            
            message += f"{status_icon} **{task['device']}**\n"
            message += f"   • Action: {task['action'].upper()}\n"
            message += f"   • Waktu: {task['time']}\n"
            message += f"   • Hari: {days_str}\n\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="time_schedule_menu"))
    
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "delete_time_schedule")
def delete_time_schedule(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "🗑️ Delete Time Schedule")
    
    if not scheduled_tasks:
        bot.edit_message_text(
            "❌ Tidak ada schedule yang dikonfigurasi.",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    markup = types.InlineKeyboardMarkup()
    for task_id, task in scheduled_tasks.items():
        label = f"{task['device']} - {task['time']} ({task['action']})"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"delete_schedule_task:{task_id}"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="time_schedule_menu"))
    
    bot.edit_message_text(
        "🗑️ *DELETE TIME SCHEDULE*\n\nPilih schedule yang ingin dihapus:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("delete_schedule_task:"))
def delete_schedule_task(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    task_id = call.data.split(":", 1)[1]
    
    if task_id in scheduled_tasks:
        del scheduled_tasks[task_id]
        
        # Simpan ke file
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(scheduled_tasks, f, indent=2)
        
        bot.answer_callback_query(call.id, "✅ Schedule dihapus")
        bot.edit_message_text(
            f"✅ Schedule **{task_id}** berhasil dihapus.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
    else:
        bot.answer_callback_query(call.id, "❌ Schedule tidak ditemukan")
        bot.edit_message_text(
            "❌ Schedule tidak ditemukan.",
            call.message.chat.id,
            call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data == "set_auto_restart")
def set_auto_restart(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "📝 Set Auto Restart")
    
    # Tampilkan pilihan device
    if not devices:
        bot.edit_message_text(
            "❌ Tidak ada device yang dikonfigurasi.\n\nTambahkan device terlebih dahulu menggunakan /adddevice",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    markup = types.InlineKeyboardMarkup()
    for device_name in devices.keys():
        status = "✅ Aktif" if auto_restart_settings.get(device_name, {}).get("enabled", False) else "❌ Nonaktif"
        markup.add(types.InlineKeyboardButton(f"{device_name} ({status})", callback_data=f"select_device_restart:{device_name}"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="auto_restart_menu"))
    
    bot.edit_message_text(
        "🔄 *SET AUTO RESTART*\n\nPilih device yang ingin diatur auto restart:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("select_device_restart:"))
def select_device_restart(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    device_name = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    
    # Mulai flow input interval
    auto_restart_state[chat_id] = {"step": 1, "data": {"device": device_name}}
    
    bot.answer_callback_query(call.id, f"📝 Device: {device_name}")
    bot.edit_message_text(
        f"🔄 *SET AUTO RESTART*\n\nDevice: **{device_name}**\n\nMasukkan interval dalam jam (contoh: 6 untuk setiap 6 jam):",
        chat_id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.chat.id in auto_restart_state and auto_restart_state[m.chat.id]["step"] == 1)
def process_auto_restart_interval(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        auto_restart_state.pop(m.chat.id, None)
        return
    
    try:
        interval = float(m.text)
        if interval < 0.5:
            bot.reply_to(m, "❌ Interval minimal 0.5 jam (30 menit). Silakan coba lagi:")
            return
        if interval > 168:
            bot.reply_to(m, "❌ Interval maksimal 168 jam (7 hari). Silakan coba lagi:")
            return
        
        state = auto_restart_state[m.chat.id]
        device_name = state["data"]["device"]
        
        # Simpan konfigurasi
        # Setiap interval akan selalu: stop → tunggu 5 detik → start
        auto_restart_settings[device_name] = {
            "enabled": True,
            "interval_hours": interval,
            "delay_seconds": 5,  # Default delay 5 detik antara stop dan start
            "last_run": int(time.time())
        }
        
        # Simpan ke file
        with open(AUTO_RESTART_FILE, "w") as f:
            json.dump(auto_restart_settings, f, indent=2)
        
        # Hapus state
        auto_restart_state.pop(m.chat.id, None)
        
        bot.reply_to(m, f"✅ Auto restart berhasil diatur untuk device **{device_name}**!\n\n"
                       f"📊 Konfigurasi:\n"
                       f"• Interval: {interval} jam\n"
                       f"• Delay: 5 detik (antara stop dan start)\n"
                       f"• Status: ✅ Aktif\n\n"
                       f"Setiap {interval} jam, EarnApp akan:\n"
                       f"1. 🔴 STOP\n"
                       f"2. ⏳ Tunggu 5 detik\n"
                       f"3. 🟢 START\n\n"
                       f"Tidak peduli status EarnApp saat ini, akan tetap dijalankan stop → start.",
                 parse_mode="Markdown")
    except ValueError:
        bot.reply_to(m, "❌ Format tidak valid. Masukkan angka (contoh: 6 untuk 6 jam):")

@bot.callback_query_handler(func=lambda call: call.data == "list_auto_restart")
def list_auto_restart(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "📋 List Auto Restart")
    
    if not auto_restart_settings:
        message = "🔄 *AUTO RESTART SETTINGS*\n\n❌ Tidak ada auto restart yang dikonfigurasi."
    else:
        message = "🔄 *AUTO RESTART SETTINGS*\n\n"
        for device_name, settings in auto_restart_settings.items():
            if settings.get("enabled", False):
                interval = settings.get("interval_hours", 0)
                delay_seconds = settings.get("delay_seconds", 5)
                last_run = settings.get("last_run", 0)
                
                if last_run > 0:
                    time_ago = int(time.time()) - last_run
                    hours_ago = time_ago // 3600
                    mins_ago = (time_ago % 3600) // 60
                    last_run_str = f"{hours_ago}j {mins_ago}m lalu"
                else:
                    last_run_str = "Belum pernah"
                
                message += f"✅ **{device_name}**\n"
                message += f"   • Interval: {interval} jam\n"
                message += f"   • Delay: {delay_seconds} detik\n"
                message += f"   • Last run: {last_run_str}\n"
                message += f"   • Action: STOP → wait → START\n\n"
            else:
                message += f"❌ **{device_name}** (Nonaktif)\n\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="auto_restart_menu"))
    
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "disable_auto_restart")
def disable_auto_restart(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "❌ Disable Auto Restart")
    
    # Tampilkan pilihan device untuk disable
    active_devices = [name for name, settings in auto_restart_settings.items() if settings.get("enabled", False)]
    
    if not active_devices:
        bot.edit_message_text(
            "❌ Tidak ada auto restart yang aktif.\n\nSemua device sudah nonaktif.",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    markup = types.InlineKeyboardMarkup()
    for device_name in active_devices:
        markup.add(types.InlineKeyboardButton(f"❌ {device_name}", callback_data=f"disable_device_restart:{device_name}"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="auto_restart_menu"))
    
    bot.edit_message_text(
        "❌ *DISABLE AUTO RESTART*\n\nPilih device yang ingin dinonaktifkan:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("disable_device_restart:"))
def disable_device_restart(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    device_name = call.data.split(":", 1)[1]
    
    if device_name in auto_restart_settings:
        auto_restart_settings[device_name]["enabled"] = False
        
        # Simpan ke file
        with open(AUTO_RESTART_FILE, "w") as f:
            json.dump(auto_restart_settings, f, indent=2)
        
        bot.answer_callback_query(call.id, f"✅ {device_name} dinonaktifkan")
        bot.edit_message_text(
            f"✅ Auto restart untuk device **{device_name}** telah dinonaktifkan.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
    else:
        bot.answer_callback_query(call.id, "❌ Device tidak ditemukan")
        bot.edit_message_text(
            f"❌ Device '{device_name}' tidak ditemukan dalam konfigurasi auto restart.",
            call.message.chat.id,
            call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data == "list_schedule")
def list_schedule(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "📋 List Schedule")
    
    message = "⏰ *SCHEDULED TASKS*\n\n"
    
    # Tampilkan auto restart settings
    active_auto_restart = [name for name, settings in auto_restart_settings.items() if settings.get("enabled", False)]
    if active_auto_restart:
        message += "🔄 *AUTO RESTART (Interval)*\n"
        for device_name in active_auto_restart:
            interval = auto_restart_settings[device_name].get("interval_hours", 0)
            message += f"✅ **{device_name}**: Setiap {interval} jam\n"
        message += "\n"
    
    # Tampilkan time-based scheduled tasks
    active_time_schedules = [task for task in scheduled_tasks.values() if task.get("enabled", True)]
    if active_time_schedules:
        message += "🕐 *TIME-BASED SCHEDULE*\n"
        days_names = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
        for task in active_time_schedules:
            days = task.get("days", [])
            days_str = ", ".join([days_names[d] for d in days]) if days else "Tidak ada"
            message += f"✅ **{task['device']}** - {task['time']} ({task['action'].upper()}) - {days_str}\n"
        message += "\n"
    
    if not active_auto_restart and not active_time_schedules:
        message += "❌ Tidak ada jadwal yang dikonfigurasi."
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_schedule"))
    
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "delete_schedule")
def delete_schedule(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "📝 Fitur delete schedule akan segera tersedia")
    bot.edit_message_text(
        "⏰ *DELETE SCHEDULE*\n\nFitur ini akan segera tersedia dalam update berikutnya.\n\nGunakan menu lain untuk mengontrol EarnApp.",
        call.message.chat.id, 
        call.message.message_id, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "schedule_settings")
def schedule_settings(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    message = "⚙️ *SCHEDULE SETTINGS*\n\n"
    message += f"🔔 Alert Enabled: {'✅' if alert_settings['enabled'] else '❌'}\n"
    message += f"⏱️ Check Interval: {alert_settings['check_interval']} detik\n"
    message += f"🚨 Offline Threshold: {alert_settings['offline_threshold']} detik\n\n"
    message += "Gunakan menu lain untuk mengontrol EarnApp."
    
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# Background monitoring task
def background_monitor():
    """Background task untuk monitoring dan alert"""
    while True:
        try:
            # Cek alert
            check_alerts()
            
            # Sleep sesuai interval
            time.sleep(alert_settings["check_interval"])
        except Exception as e:
            print(f"Error in background monitor: {e}")
            time.sleep(60)  # Sleep 1 menit jika error

# Background auto restart task
def background_auto_restart():
    """Background task untuk auto restart EarnApp setiap beberapa jam"""
    while True:
        try:
            current_time = int(time.time())
            
            for device_name, settings in auto_restart_settings.items():
                if not settings.get("enabled", False):
                    continue
                
                interval_hours = settings.get("interval_hours", 0)
                if interval_hours <= 0:
                    continue
                
                last_run = settings.get("last_run", 0)
                interval_seconds = int(interval_hours * 3600)
                delay_seconds = settings.get("delay_seconds", 5)  # Default 5 detik delay antara stop dan start
                
                # Cek apakah sudah waktunya untuk menjalankan
                if current_time - last_run >= interval_seconds:
                    # Selalu jalankan: stop → tunggu → start
                    print(f"Auto restart: {device_name} - Executing stop → wait {delay_seconds}s → start")
                    
                    # 1. Jalankan stop (tidak peduli status saat ini)
                    stop_result = stop_earnapp_device(device_name)
                    print(f"Auto restart: {device_name} - Stop executed")
                    
                    # 2. Tunggu beberapa detik
                    time.sleep(delay_seconds)
                    
                    # 3. Jalankan start
                    start_result = start_earnapp_device(device_name)
                    print(f"Auto restart: {device_name} - Start executed")
                    
                    # Log activity
                    log_activity(device_name, "restart", f"Stop: {stop_result[:200]}\nStart: {start_result[:200]}", "auto", "system")
                    
                    # Update settings
                    auto_restart_settings[device_name]["last_run"] = current_time
                    
                    # Simpan ke file
                    try:
                        with open(AUTO_RESTART_FILE, "w") as f:
                            json.dump(auto_restart_settings, f, indent=2)
                    except Exception as e:
                        print(f"Error saving auto_restart.json: {e}")
                    
                    # Kirim notifikasi ke admin
                    if ADMIN_ID:
                        try:
                            bot.send_message(
                                ADMIN_ID,
                                f"🔄 *AUTO RESTART*\n\n"
                                f"Device: **{device_name}**\n"
                                f"Interval: {interval_hours} jam\n"
                                f"Delay: {delay_seconds} detik\n\n"
                                f"**Stop Result:**\n```\n{stop_result}\n```\n\n"
                                f"**Start Result:**\n```\n{start_result}\n```",
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            print(f"Error sending auto restart notification: {e}")
                    
                    print(f"Auto restart: {device_name} - Completed (stop → wait → start)")
            
            # Sleep 1 menit sebelum cek lagi
            time.sleep(60)
        except Exception as e:
            print(f"Error in background auto restart: {e}")
            time.sleep(60)  # Sleep 1 menit jika error

# Background time-based schedule task
def background_time_schedule():
    """Background task untuk menjalankan time-based schedule"""
    # Track last execution untuk setiap task
    last_executions = {}  # task_id -> timestamp
    
    while True:
        try:
            from datetime import datetime
            
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            current_weekday = current_time.weekday()  # 0=Monday, 6=Sunday
            
            for task_id, task in scheduled_tasks.items():
                if not task.get("enabled", True):
                    continue
                
                # Parse waktu dari task
                time_str = task.get("time", "")
                if not time_str:
                    continue
                
                try:
                    task_hour, task_minute = map(int, time_str.split(":"))
                except (ValueError, IndexError):
                    continue
                
                # Cek apakah hari sesuai
                task_days = task.get("days", [])
                if current_weekday not in task_days:
                    continue
                
                # Cek apakah waktu sudah sesuai (dalam 1 menit toleransi)
                if current_hour == task_hour and current_minute == task_minute:
                    # Cek apakah sudah dijalankan dalam 1 menit terakhir (hindari duplikasi)
                    last_exec = last_executions.get(task_id, 0)
                    if int(time.time()) - last_exec < 60:
                        continue
                    
                    # Jalankan action
                    device_name = task.get("device")
                    action = task.get("action", "restart")
                    
                    print(f"Time schedule: {task_id} - Executing {action} on {device_name}")
                    
                    if action == "restart":
                        # Restart: stop → wait 5s → start
                        stop_result = stop_earnapp_device(device_name)
                        time.sleep(5)
                        start_result = start_earnapp_device(device_name)
                        
                        # Log activity
                        log_activity(device_name, "restart", f"Stop: {stop_result[:200]}\nStart: {start_result[:200]}", "scheduled", "system")
                        
                        # Kirim notifikasi
                        if ADMIN_ID:
                            try:
                                bot.send_message(
                                    ADMIN_ID,
                                    f"🔄 *TIME SCHEDULE*\n\n"
                                    f"Task: **{task_id}**\n"
                                    f"Device: **{device_name}**\n"
                                    f"Action: RESTART\n"
                                    f"Waktu: {time_str}\n\n"
                                    f"**Stop Result:**\n```\n{stop_result}\n```\n\n"
                                    f"**Start Result:**\n```\n{start_result}\n```",
                                    parse_mode="Markdown"
                                )
                            except Exception as e:
                                print(f"Error sending time schedule notification: {e}")
                    
                    elif action == "start":
                        result = start_earnapp_device(device_name)
                        
                        # Log activity
                        log_activity(device_name, "start", result, "scheduled", "system")
                        
                        if ADMIN_ID:
                            try:
                                bot.send_message(
                                    ADMIN_ID,
                                    f"🟢 *TIME SCHEDULE*\n\n"
                                    f"Task: **{task_id}**\n"
                                    f"Device: **{device_name}**\n"
                                    f"Action: START\n"
                                    f"Waktu: {time_str}\n\n"
                                    f"**Result:**\n```\n{result}\n```",
                                    parse_mode="Markdown"
                                )
                            except Exception as e:
                                print(f"Error sending time schedule notification: {e}")
                    
                    elif action == "stop":
                        result = stop_earnapp_device(device_name)
                        
                        # Log activity
                        log_activity(device_name, "stop", result, "scheduled", "system")
                        
                        if ADMIN_ID:
                            try:
                                bot.send_message(
                                    ADMIN_ID,
                                    f"🔴 *TIME SCHEDULE*\n\n"
                                    f"Task: **{task_id}**\n"
                                    f"Device: **{device_name}**\n"
                                    f"Action: STOP\n"
                                    f"Waktu: {time_str}\n\n"
                                    f"**Result:**\n```\n{result}\n```",
                                    parse_mode="Markdown"
                                )
                            except Exception as e:
                                print(f"Error sending time schedule notification: {e}")
                    
                    # Update last execution
                    last_executions[task_id] = int(time.time())
                    print(f"Time schedule: {task_id} - Completed")
            
            # Sleep 30 detik sebelum cek lagi (lebih sering untuk akurasi waktu)
            time.sleep(30)
        except Exception as e:
            print(f"Error in background time schedule: {e}")
            time.sleep(60)  # Sleep 1 menit jika error

# Activity Log & History
@bot.message_handler(func=lambda m: m.text == "📝 Activity Log")
def handler_activity_log(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    # Tampilkan menu activity log
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📋 View History", callback_data="view_activity_log"),
        types.InlineKeyboardButton("🔍 Filter by Device", callback_data="filter_log_device")
    )
    markup.add(
        types.InlineKeyboardButton("📅 Filter by Date", callback_data="filter_log_date"),
        types.InlineKeyboardButton("💾 Export Log", callback_data="export_log")
    )
    markup.add(
        types.InlineKeyboardButton("🗑️ Clear Log", callback_data="clear_log")
    )
    
    total_logs = len(activity_logs)
    bot.reply_to(m, f"📝 *ACTIVITY LOG*\n\nTotal logs: **{total_logs}**\n\nPilih opsi di bawah ini:", 
                 parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "view_activity_log")
def view_activity_log(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "📋 Loading history...")
    
    if not activity_logs:
        bot.edit_message_text(
            "📝 *ACTIVITY LOG*\n\n❌ Tidak ada log yang tersedia.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        return
    
    # Tampilkan 10 log terakhir
    from datetime import datetime
    recent_logs = activity_logs[-10:]
    message = "📝 *ACTIVITY LOG (10 Terakhir)*\n\n"
    
    for log in reversed(recent_logs):
        timestamp = datetime.fromtimestamp(log["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        action_icon = {"start": "🟢", "stop": "🔴", "restart": "🔄"}.get(log["action"], "⚙️")
        type_icon = {"manual": "👤", "auto": "🤖", "scheduled": "⏰"}.get(log["type"], "❓")
        
        message += f"{action_icon} {type_icon} **{log['device']}** - {log['action'].upper()}\n"
        message += f"   📅 {timestamp}\n"
        message += f"   👤 {log['user']}\n\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_activity_log"))
    
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "filter_log_device")
def filter_log_device(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "🔍 Filter by Device")
    
    if not devices:
        bot.edit_message_text(
            "❌ Tidak ada device yang dikonfigurasi.",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    markup = types.InlineKeyboardMarkup()
    for device_name in devices.keys():
        # Hitung jumlah log per device
        count = sum(1 for log in activity_logs if log.get("device") == device_name)
        markup.add(types.InlineKeyboardButton(f"{device_name} ({count})", callback_data=f"view_log_device:{device_name}"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_activity_log"))
    
    bot.edit_message_text(
        "🔍 *FILTER BY DEVICE*\n\nPilih device untuk melihat history:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("view_log_device:"))
def view_log_device(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    device_name = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id, f"Loading {device_name} logs...")
    
    # Filter logs by device
    device_logs = [log for log in activity_logs if log.get("device") == device_name]
    
    if not device_logs:
        bot.edit_message_text(
            f"📝 *ACTIVITY LOG*\n\nDevice: **{device_name}**\n\n❌ Tidak ada log untuk device ini.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        return
    
    # Tampilkan 20 log terakhir untuk device ini
    from datetime import datetime
    recent_logs = device_logs[-20:]
    message = f"📝 *ACTIVITY LOG*\n\nDevice: **{device_name}**\nTotal: {len(device_logs)} logs\n\n"
    
    for log in reversed(recent_logs):
        timestamp = datetime.fromtimestamp(log["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        action_icon = {"start": "🟢", "stop": "🔴", "restart": "🔄"}.get(log["action"], "⚙️")
        type_icon = {"manual": "👤", "auto": "🤖", "scheduled": "⏰"}.get(log["type"], "❓")
        
        message += f"{action_icon} {type_icon} {log['action'].upper()}\n"
        message += f"   📅 {timestamp}\n\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="filter_log_device"))
    
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "filter_log_date")
def filter_log_date(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "📅 Filter by Date")
    filter_date_state[call.message.chat.id] = True
    
    bot.edit_message_text(
        "📅 *FILTER BY DATE*\n\nMasukkan tanggal dalam format YYYY-MM-DD (contoh: 2024-01-15):\n\nAtau gunakan:\n• 'today' untuk hari ini\n• 'yesterday' untuk kemarin\n• 'week' untuk 7 hari terakhir",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.chat.id in filter_date_state)
def process_filter_date(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        filter_date_state.pop(m.chat.id, None)
        return
    
    date_input = m.text.strip().lower()
    from datetime import datetime, timedelta
    
    try:
        if date_input == "today":
            target_date = datetime.now().date()
        elif date_input == "yesterday":
            target_date = (datetime.now() - timedelta(days=1)).date()
        elif date_input == "week":
            # Filter untuk 7 hari terakhir
            target_date = None
            days_ago = 7
        else:
            # Parse tanggal
            target_date = datetime.strptime(date_input, "%Y-%m-%d").date()
            days_ago = None
        
        # Filter logs
        if days_ago:
            # Filter untuk N hari terakhir
            cutoff_time = int((datetime.now() - timedelta(days=days_ago)).timestamp())
            filtered_logs = [log for log in activity_logs if log["timestamp"] >= cutoff_time]
            date_str = f"{days_ago} hari terakhir"
        else:
            # Filter untuk tanggal tertentu
            start_time = int(datetime.combine(target_date, datetime.min.time()).timestamp())
            end_time = int(datetime.combine(target_date, datetime.max.time()).timestamp())
            filtered_logs = [log for log in activity_logs if start_time <= log["timestamp"] <= end_time]
            date_str = target_date.strftime("%Y-%m-%d")
        
        if not filtered_logs:
            bot.reply_to(m, f"📅 *FILTER BY DATE*\n\nTanggal: **{date_str}**\n\n❌ Tidak ada log untuk tanggal tersebut.",
                       parse_mode="Markdown")
            filter_date_state.pop(m.chat.id, None)
            return
        
        # Tampilkan hasil (maksimal 30 log)
        display_logs = filtered_logs[-30:]
        message = f"📅 *FILTER BY DATE*\n\nTanggal: **{date_str}**\nTotal: **{len(filtered_logs)}** logs\n\n"
        
        for log in reversed(display_logs):
            timestamp = datetime.fromtimestamp(log["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            action_icon = {"start": "🟢", "stop": "🔴", "restart": "🔄"}.get(log["action"], "⚙️")
            type_icon = {"manual": "👤", "auto": "🤖", "scheduled": "⏰"}.get(log["type"], "❓")
            
            message += f"{action_icon} {type_icon} **{log['device']}** - {log['action'].upper()}\n"
            message += f"   📅 {timestamp}\n\n"
        
        if len(filtered_logs) > 30:
            message += f"\n_*Menampilkan 30 dari {len(filtered_logs)} logs_"
        
        filter_date_state.pop(m.chat.id, None)
        bot.reply_to(m, message, parse_mode="Markdown")
        
    except ValueError:
        bot.reply_to(m, "❌ Format tanggal tidak valid. Gunakan format YYYY-MM-DD (contoh: 2024-01-15) atau 'today'/'yesterday'/'week':")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")
        filter_date_state.pop(m.chat.id, None)

@bot.callback_query_handler(func=lambda call: call.data == "export_log")
def export_log(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "💾 Exporting log...")
    
    if not activity_logs:
        bot.edit_message_text(
            "❌ Tidak ada log yang tersedia untuk diekspor.",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    # Export ke JSON
    try:
        export_file = "activity_log_export.json"
        with open(export_file, "w") as f:
            json.dump(activity_logs, f, indent=2)
        
        # Export ke CSV juga
        import csv
        csv_file = "activity_log_export.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Date", "Time", "Device", "Action", "Type", "User", "Result"])
            
            from datetime import datetime
            for log in activity_logs:
                dt = datetime.fromtimestamp(log["timestamp"])
                writer.writerow([
                    log["timestamp"],
                    dt.strftime("%Y-%m-%d"),
                    dt.strftime("%H:%M:%S"),
                    log.get("device", ""),
                    log.get("action", ""),
                    log.get("type", ""),
                    log.get("user", ""),
                    log.get("result", "")[:200]  # Limit result length
                ])
        
        bot.edit_message_text(
            f"✅ *EXPORT LOG SELESAI*\n\n"
            f"File yang dibuat:\n"
            f"• `{export_file}` (JSON)\n"
            f"• `{csv_file}` (CSV)\n\n"
            f"Total logs: **{len(activity_logs)}**\n\n"
            f"File tersimpan di direktori bot.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.edit_message_text(
            f"❌ Error saat export log: {e}",
            call.message.chat.id,
            call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data == "clear_log")
def clear_log(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    # Konfirmasi clear
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ya, Hapus Semua", callback_data="confirm_clear_log"),
        types.InlineKeyboardButton("❌ Batal", callback_data="back_to_activity_log")
    )
    
    bot.edit_message_text(
        f"⚠️ *CLEAR ACTIVITY LOG*\n\nApakah Anda yakin ingin menghapus semua log?\n\nTotal logs: **{len(activity_logs)}**\n\n**Peringatan:** Tindakan ini tidak dapat dibatalkan!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_clear_log")
def confirm_clear_log(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    global activity_logs
    count = len(activity_logs)
    activity_logs.clear()
    
    # Simpan ke file
    with open(ACTIVITY_LOG_FILE, "w") as f:
        json.dump(activity_logs, f, indent=2)
    
    bot.answer_callback_query(call.id, "✅ Log dihapus")
    bot.edit_message_text(
        f"✅ *CLEAR LOG SELESAI*\n\nBerhasil menghapus **{count}** log entries.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_activity_log")
def back_to_activity_log(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses")
        return
    
    bot.answer_callback_query(call.id, "🔙 Kembali")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📋 View History", callback_data="view_activity_log"),
        types.InlineKeyboardButton("🔍 Filter by Device", callback_data="filter_log_device")
    )
    markup.add(
        types.InlineKeyboardButton("📅 Filter by Date", callback_data="filter_log_date"),
        types.InlineKeyboardButton("💾 Export Log", callback_data="export_log")
    )
    markup.add(
        types.InlineKeyboardButton("🗑️ Clear Log", callback_data="clear_log")
    )
    
    total_logs = len(activity_logs)
    bot.edit_message_text(
        f"📝 *ACTIVITY LOG*\n\nTotal logs: **{total_logs}**\n\nPilih opsi di bawah ini:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

# Handler untuk restart bot
@bot.message_handler(func=lambda m: m.text == "🔄 Restart Bot")
def handler_restart_bot(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    # Konfirmasi restart
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ya, Restart", callback_data="confirm_restart"),
        types.InlineKeyboardButton("❌ Batal", callback_data="cancel_restart")
    )
    bot.reply_to(m, "⚠️ *Konfirmasi Restart Bot*\n\nApakah Anda yakin ingin me-restart bot?\n\nBot akan berhenti sebentar dan memuat ulang konfigurasi.", 
                 parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_restart")
def confirm_restart(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "🔄 Memulai restart bot...")
    
    # Kirim pesan restart
    bot.edit_message_text(
        "🔄 *Restart Bot*\n\nBot sedang di-restart...\nSilakan tunggu beberapa detik.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )
    
    # Simpan semua state ke file
    try:
        # Simpan devices.json
        with open(DEVICE_FILE, "w") as f:
            json.dump(devices, f, indent=2)
        # Simpan auto_restart.json
        with open(AUTO_RESTART_FILE, "w") as f:
            json.dump(auto_restart_settings, f, indent=2)
        # Simpan schedules.json
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(scheduled_tasks, f, indent=2)
        # Simpan activity_log.json
        with open(ACTIVITY_LOG_FILE, "w") as f:
            json.dump(activity_logs, f, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}")
    
    # Stop polling dan batalkan semua tasks
    try:
        bot.stop_polling()
    except Exception as e:
        print(f"Error stopping bot: {e}")
    
    # Restart process
    try:
        import sys
        import os
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception as e:
        print(f"Error restarting: {e}")
        # Jika gagal restart, coba exit saja (service manager akan restart)
        sys.exit(1)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_restart")
def cancel_restart(call):
    bot.answer_callback_query(call.id, "❌ Restart dibatalkan")
    bot.edit_message_text(
        "❌ Restart bot dibatalkan.",
        call.message.chat.id,
        call.message.message_id
    )

# Fallback
@bot.message_handler(func=lambda m: True)
def fallback(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    bot.reply_to(m, "Gunakan tombol menu untuk mengontrol EarnApp 👇")
    show_main_menu(m.chat.id)

# -----------------------
# Cleanup dan Shutdown
# -----------------------
def cleanup():
    """Cleanup sebelum shutdown/restart"""
    try:
        # Simpan state
        with open(DEVICE_FILE, "w") as f:
            json.dump(devices, f, indent=2)
        
        # Simpan auto restart settings
        with open(AUTO_RESTART_FILE, "w") as f:
            json.dump(auto_restart_settings, f, indent=2)
        
        # Simpan scheduled tasks
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(scheduled_tasks, f, indent=2)
        
        # Simpan activity logs
        with open(ACTIVITY_LOG_FILE, "w") as f:
            json.dump(activity_logs, f, indent=2)
        
        # Hapus state sementara
        add_device_state.clear()
        remove_device_state.clear()
        auto_restart_state.clear()
        schedule_state.clear()
        filter_date_state.clear()
        
        # Stop bot polling
        try:
            bot.stop_polling()
        except Exception:
            pass
            
    except Exception as e:
        print(f"Error during cleanup: {e}")

# -----------------------
# Run bot
# -----------------------
if __name__ == "__main__":
    print("🤖 Bot EarnApp multi-device aktif dan mendengarkan perintah Telegram...")
    
    # Start background monitoring
    monitor_thread = threading.Thread(target=background_monitor, daemon=True)
    monitor_thread.start()
    print("🔍 Background monitoring started...")
    
    # Start background auto restart
    auto_restart_thread = threading.Thread(target=background_auto_restart, daemon=True)
    auto_restart_thread.start()
    print("🔄 Background auto restart started...")
    
    # Start background time-based schedule
    time_schedule_thread = threading.Thread(target=background_time_schedule, daemon=True)
    time_schedule_thread.start()
    print("🕐 Background time-based schedule started...")
    
    # Kirim notifikasi bahwa bot sudah siap (setelah delay untuk memastikan bot sudah ready)
    def send_ready_notification():
        """Kirim notifikasi bahwa bot sudah siap digunakan"""
        time.sleep(3)  # Tunggu 3 detik untuk memastikan bot sudah ready
        if ADMIN_ID:
            try:
                from datetime import datetime
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                bot.send_message(
                    ADMIN_ID,
                    f"✅ *BOT READY*\n\n"
                    f"Bot EarnApp telah siap digunakan!\n\n"
                    f"📅 Waktu: {current_time}\n"
                    f"🔄 Status: Online\n\n"
                    f"Semua fitur sudah aktif dan siap digunakan.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Error sending ready notification: {e}")
    
    # Start thread untuk kirim notifikasi ready
    ready_thread = threading.Thread(target=send_ready_notification, daemon=True)
    ready_thread.start()
    
    # Start bot
    bot.infinity_polling()
