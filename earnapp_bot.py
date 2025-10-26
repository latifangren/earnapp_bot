#!/usr/bin/env python3
import os
import json
import telebot
import subprocess
from telebot import types
import paramiko
import time
import threading

# -----------------------
# Load konfigurasi dari file
# -----------------------
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
# Full path executable EarnApp
# -----------------------
EARNAPP_CMD = "/usr/bin/earnapp"

# -----------------------
# File untuk menyimpan device
# -----------------------
DEVICE_FILE = "devices.json"

if os.path.exists(DEVICE_FILE):
    with open(DEVICE_FILE, "r") as f:
        devices = json.load(f)
else:
    devices = {"SERVER": {"type": "local", "path": "/usr/bin"}}
    with open(DEVICE_FILE, "w") as f:
        json.dump(devices, f, indent=2)

user_device = {}
add_device_state = {}
scheduled_tasks = {}
device_health = {}

alert_settings = {
    "enabled": True,
    "offline_threshold": 300,
    "check_interval": 60
}

# -----------------------
# Fungsi menjalankan perintah
# -----------------------
def run_cmd_local(cmd):
    try:
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
    try:
        result = run_cmd_device_by_name(device_name, f"{EARNAPP_CMD} status")
        if result:
            device_health[device_name] = {"status": "online", "last_check": int(time.time()), "error": None}
            return True
        else:
            device_health[device_name] = {"status": "offline", "last_check": int(time.time()), "error": "Command failed"}
            return False
    except Exception as e:
        device_health[device_name] = {"status": "offline", "last_check": int(time.time()), "error": str(e)}
        return False

def get_dashboard_data():
    dashboard_data = []
    for device_name in devices.keys():
        is_healthy = check_device_health(device_name)
        earnapp_status = run_cmd_device_by_name(device_name, f"{EARNAPP_CMD} status")
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
    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🚨 *ALERT*\n\n{message}", parse_mode="Markdown")
        except Exception as e:
            print(f"Error sending alert: {e}")

def check_alerts():
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
        types.KeyboardButton("🗑️ Uninstall Bot")
    )
    bot.send_message(chat_id, "Silakan pilih menu di bawah ini 👇", reply_markup=markup)

def show_device_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for name in devices.keys():
        markup.add(types.KeyboardButton(name))
    bot.send_message(chat_id, "Pilih device yang ingin dikontrol:", reply_markup=markup)

# -----------------------
# Handlers (semua command sudah pakai EARNAPP_CMD)
# -----------------------
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    if ADMIN_ID and str(msg.from_user.id) != str(ADMIN_ID):
        bot.reply_to(msg, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    bot.reply_to(msg, "🤖 Bot EarnApp aktif! Pilih device yang ingin dikontrol.")
    show_device_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.text in devices)
def select_device(m):
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    user_device[m.chat.id] = m.text
    bot.send_message(m.chat.id, f"✅ Device '{m.text}' dipilih.")
    show_main_menu(m.chat.id)

@bot.message_handler(func=lambda m: m.text == "🟡 Status")
def handler_status(m):
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    out = run_cmd_device(m.chat.id, f"{EARNAPP_CMD} status")
    bot.reply_to(m, f"📊 *Status ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🟢 Start EarnApp")
def handler_start(m):
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    run_cmd_device(m.chat.id, f"{EARNAPP_CMD} start")
    out = run_cmd_device(m.chat.id, f"{EARNAPP_CMD} status")
    bot.reply_to(m, f"🟢 *Menjalankan EarnApp ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔴 Stop EarnApp")
def handler_stop(m):
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    run_cmd_device(m.chat.id, f"{EARNAPP_CMD} stop")
    out = run_cmd_device(m.chat.id, f"{EARNAPP_CMD} status")
    bot.reply_to(m, f"🔴 *Menghentikan EarnApp ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📱 Register")
def handler_register(m):
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    out = run_cmd_device(m.chat.id, f"{EARNAPP_CMD} register")
    bot.reply_to(m, f"📱 *Register ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🆔 Show ID")
def handler_showid(m):
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    out = run_cmd_device(m.chat.id, f"{EARNAPP_CMD} showid")
    bot.reply_to(m, f"🆔 *Device ID ({user_device.get(m.chat.id, '—')}):*\n```\n{out}\n```", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💣 Uninstall")
def handler_uninstall(m):
    if ADMIN_ID and str(m.from_user.id) != str(ADMIN_ID):
        bot.reply_to(m, "❌ Anda tidak memiliki akses ke bot ini.")
        return
    run_cmd_device(m.chat.id, f"{EARNAPP_CMD} uninstall")
    bot.reply_to(m, f"💣 *Uninstall selesai ({user_device.get(m.chat.id, '—')}).*")

@bot.message_handler(func=lambda m: m.text == "📊 Dashboard")
def handler_dashboard(m):
    data = get_dashboard_data()
    msg_text = "📊 *Dashboard Devices:*\n"
    for d in data:
        msg_text += f"{d['health']} {d['earnapp']} {d['name']}: {d['status']}\n"
    bot.send_message(m.chat.id, msg_text, parse_mode="Markdown")

# -----------------------
# Threading: auto health check
# -----------------------
def auto_health_check():
    while True:
        for dev_name in devices.keys():
            check_device_health(dev_name)
        check_alerts()
        time.sleep(alert_settings["check_interval"])

t = threading.Thread(target=auto_health_check, daemon=True)
t.start()

# -----------------------
# Start polling
# -----------------------
print("🤖 Bot berjalan...")

bot.infinity_polling()
