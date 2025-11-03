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

# Menyimpan scheduled tasks
scheduled_tasks = {}  # task_id -> {"device": "name", "action": "start/stop", "time": "HH:MM", "days": [1,2,3,4,5]}

# Menyimpan device health status
device_health = {}  # device_name -> {"status": "online/offline", "last_check": timestamp, "error": "message"}

# Menyimpan alert settings
alert_settings = {
    "enabled": True,
    "offline_threshold": 300,  # 5 menit
    "check_interval": 60  # 1 menit
}

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
    else:
        return "❌ Tipe device tidak dikenali."

def check_device_health(device_name):
    """Cek kesehatan device"""
    try:
        # Test koneksi dengan command sederhana
        result = run_cmd_device_by_name(device_name, "echo 'health_check'")
        if "health_check" in result:
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
                "error": "Command failed"
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
        # Cek kesehatan device
        is_healthy = check_device_health(device_name)
        
        # Dapatkan status EarnApp
        earnapp_status = run_cmd_device_by_name(device_name, "earnapp status")
        
        # Parse status untuk mendapatkan info penting
        status_icon = "🟢" if is_healthy else "🔴"
        earnapp_icon = "🟢" if "running" in earnapp_status.lower() else "🔴"
        
        dashboard_data.append({
            "name": device_name,
            "health": status_icon,
            "earnapp": earnapp_icon,
            "status": earnapp_status[:100] + "..." if len(earnapp_status) > 100 else earnapp_status
        })
    
    return dashboard_data

def send_alert(chat_id, message):
    """Kirim alert ke admin"""
    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🚨 *ALERT*\n\n{message}", parse_mode="Markdown")
        except Exception as e:
            print(f"Error sending alert: {e}")

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
        types.KeyboardButton("📊 Dashboard")
    )
    markup.add(
        types.KeyboardButton("📱 Register"),
        types.KeyboardButton("🆔 Show ID"),
        types.KeyboardButton("💣 Uninstall"),
        types.KeyboardButton("🔄 Ganti Device")
    )
    markup.add(
        types.KeyboardButton("🚀 Start All"),
        types.KeyboardButton("🛑 Stop All"),
        types.KeyboardButton("🔍 Health Check"),
        types.KeyboardButton("⏰ Schedule")
    )
    markup.add(
        types.KeyboardButton("/adddevice"),
        types.KeyboardButton("🗑️ Remove Device"),
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
def add_device_start(msg):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(msg.from_user.id) != str(ADMIN_ID):
        bot.reply_to(msg, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    chat_id = msg.chat.id
    add_device_state[chat_id] = {"step": 1, "data": {}}
    bot.send_message(chat_id, "Masukkan IP address device:")

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

    if step == 1:
        state["data"]["host"] = msg.text
        state["step"] = 2
        bot.send_message(chat_id, "Masukkan nama device:")
    elif step == 2:
        state["data"]["name"] = msg.text
        state["step"] = 3
        bot.send_message(chat_id, "Masukkan username SSH:")
    elif step == 3:
        state["data"]["user"] = msg.text
        state["step"] = 4
        bot.send_message(chat_id, "Masukkan password SSH:")
    elif step == 4:
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
        bot.send_message(chat_id, f"✅ Device '{data['name']}' berhasil ditambahkan!")
        add_device_state.pop(chat_id)
        show_main_menu(chat_id)

# Menu kontrol
@bot.message_handler(func=lambda m: m.text == "🟡 Status")
def handler_status(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    out = run_cmd_device(m.chat.id, "earnapp status")
    bot.reply_to(m, f"📊 *Status ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🟢 Start EarnApp")
def handler_start(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    run_cmd_device(m.chat.id, "earnapp start")
    out = run_cmd_device(m.chat.id, "earnapp status")
    bot.reply_to(m, f"🟢 *Menjalankan EarnApp ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔴 Stop EarnApp")
def handler_stop(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    run_cmd_device(m.chat.id, "earnapp stop")
    out = run_cmd_device(m.chat.id, "earnapp status")
    bot.reply_to(m, f"🔴 *Menghentikan EarnApp ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📱 Register")
def handler_register(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
        
    out = run_cmd_device(m.chat.id, "earnapp register")
    bot.reply_to(m, f"📱 *Register ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

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

# Dashboard Multi-Device
@bot.message_handler(func=lambda m: m.text == "📊 Dashboard")
def handler_dashboard(m):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.reply_to(m, "🔄 Mengumpulkan data dashboard...")
    
    # Kumpulkan data dashboard
    dashboard_data = get_dashboard_data()
    
    # Format pesan dashboard
    message = "📊 *DASHBOARD MULTI-DEVICE*\n\n"
    
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
        result = run_cmd_device_by_name(device_name, "earnapp start")
        results.append(f"**{device_name}**: {result}")
    
    message = "🚀 *START ALL DEVICES*\n\n" + "\n".join(results)
    bot.reply_to(m, message, parse_mode="Markdown")

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
        result = run_cmd_device_by_name(device_name, "earnapp stop")
        results.append(f"**{device_name}**: {result}")
    
    message = "🛑 *STOP ALL DEVICES*\n\n" + "\n".join(results)
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

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
        types.InlineKeyboardButton("➕ Add Schedule", callback_data="add_schedule"),
        types.InlineKeyboardButton("📋 List Schedule", callback_data="list_schedule")
    )
    markup.add(
        types.InlineKeyboardButton("🗑️ Delete Schedule", callback_data="delete_schedule"),
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
@bot.callback_query_handler(func=lambda call: call.data == "add_schedule")
def add_schedule(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    bot.answer_callback_query(call.id, "📝 Fitur schedule akan segera tersedia")
    bot.edit_message_text(
        "⏰ *ADD SCHEDULE*\n\nFitur ini akan segera tersedia dalam update berikutnya.\n\nGunakan menu lain untuk mengontrol EarnApp.",
        call.message.chat.id, 
        call.message.message_id, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "list_schedule")
def list_schedule(call):
    # Cek apakah user adalah admin
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    
    if not scheduled_tasks:
        message = "⏰ *SCHEDULED TASKS*\n\n❌ Tidak ada jadwal yang dikonfigurasi."
    else:
        message = "⏰ *SCHEDULED TASKS*\n\n"
        for task_id, task in scheduled_tasks.items():
            message += f"🕐 **{task['time']}** - {task['action']} {task['device']}\n"
    
    bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

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
    except Exception as e:
        print(f"Error saving devices: {e}")
    
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
        
        # Hapus state sementara
        add_device_state.clear()
        remove_device_state.clear()
        
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
    
    # Start bot
    bot.infinity_polling()
