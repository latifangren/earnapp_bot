# 📋 Panduan Instalasi EarnApp Bot

## 🚀 Instalasi Cepat (Recommended)

### 1. Persiapan Server
```bash
# Update sistem
sudo apt update && sudo apt upgrade -y

# Install git jika belum ada
sudo apt install -y git
```

### 2. Clone Repository
```bash
# Clone repository
git clone https://github.com/username/earnapp_bot.git
cd earnapp_bot

# Jalankan script instalasi otomatis
sudo bash install.sh
```

### 3. Konfigurasi Bot
```bash
# Edit file konfigurasi
sudo nano /srv/earnapp_bot/config.json
```

Isi dengan data Anda:
```json
{
  "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
  "admin_telegram_id": "123456789"
}
```

### 4. Start Bot
```bash
# Start service
sudo systemctl start earnapp-bot

# Enable auto-start
sudo systemctl enable earnapp-bot

# Cek status
sudo systemctl status earnapp-bot
```

## 🔧 Instalasi Manual

### 1. Install Dependencies Sistem
```bash
# Update sistem
sudo apt update && sudo apt upgrade -y

# Install Python dan tools
sudo apt install -y python3 python3-pip python3-venv git

# Install dependencies untuk paramiko
sudo apt install -y libffi-dev libssl-dev
```

### 2. Setup Direktori
```bash
# Buat direktori
sudo mkdir -p /srv/earnapp_bot
cd /srv/earnapp_bot

# Clone repository
sudo git clone https://github.com/username/earnapp_bot.git .

# Set ownership
sudo chown -R $USER:$USER /srv/earnapp_bot
```

### 3. Setup Python Environment
```bash
cd /srv/earnapp_bot

# Buat virtual environment
python3 -m venv venv

# Aktifkan virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Konfigurasi Bot
```bash
# Copy template konfigurasi
cp config.example.json config.json

# Edit konfigurasi
nano config.json
```

Isi `config.json`:
```json
{
  "bot_token": "YOUR_BOT_TOKEN_HERE",
  "admin_telegram_id": "YOUR_TELEGRAM_ID_HERE"
}
```

### 5. Setup Systemd Service
```bash
# Buat service file
sudo nano /etc/systemd/system/earnapp-bot.service
```

Isi dengan (ganti `your_username` dengan username Anda):
```ini
[Unit]
Description=EarnApp Bot Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/srv/earnapp_bot
Environment=PATH=/srv/earnapp_bot/venv/bin
ExecStart=/srv/earnapp_bot/venv/bin/python earnapp_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 6. Enable dan Start Service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable earnapp-bot

# Start service
sudo systemctl start earnapp-bot

# Cek status
sudo systemctl status earnapp-bot
```

## 🤖 Setup Telegram Bot

### 1. Buat Bot di Telegram
1. Buka [@BotFather](https://t.me/botfather) di Telegram
2. Kirim `/newbot`
3. Masukkan nama bot (contoh: "EarnApp Controller")
4. Masukkan username bot (contoh: "earnapp_controller_bot")
5. Simpan **Bot Token** yang diberikan

### 2. Dapatkan Telegram ID
1. Buka [@userinfobot](https://t.me/userinfobot) di Telegram
2. Kirim pesan apapun
3. Bot akan mengirim **Your user ID**
4. Simpan ID tersebut

### 3. Update Konfigurasi
```bash
# Edit file konfigurasi
nano /srv/earnapp_bot/config.json
```

Isi dengan data yang didapat:
```json
{
  "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
  "admin_telegram_id": "123456789"
}
```

## 📱 Setup Device SSH

### 1. Install EarnApp di Device Target
```bash
# Di device target, install EarnApp
curl -sL https://earnapp.com/install.sh | sudo bash
```

### 2. Setup SSH di Device Target
```bash
# Install SSH server
sudo apt install -y openssh-server

# Start SSH service
sudo systemctl start ssh
sudo systemctl enable ssh

# Cek status
sudo systemctl status ssh
```

### 3. Tambah Device via Bot
1. Start bot dengan `/start`
2. Pilih device "Local" dulu
3. Kirim `/adddevice`
4. Ikuti instruksi untuk menambah device SSH

## 🔍 Troubleshooting

### Bot Tidak Start
```bash
# Cek log error
journalctl -u earnapp-bot -f

# Cek konfigurasi
cat /srv/earnapp_bot/config.json

# Test manual
cd /srv/earnapp_bot
source venv/bin/activate
python earnapp_bot.py
```

### SSH Connection Error
```bash
# Test koneksi SSH manual
ssh user@ip_address

# Cek SSH service di device target
sudo systemctl status ssh

# Cek firewall
sudo ufw status
```

### EarnApp Command Error
```bash
# Cek EarnApp terinstall
which earnapp

# Test command manual
earnapp status

# Cek permission
ls -la /usr/bin/earnapp
```

### Permission Error
```bash
# Fix ownership
sudo chown -R $USER:$USER /srv/earnapp_bot

# Fix permission
chmod +x /srv/earnapp_bot/earnapp_bot.py
```

## 📊 Monitoring

### Cek Status Service
```bash
sudo systemctl status earnapp-bot
```

### Lihat Log Real-time
```bash
journalctl -u earnapp-bot -f
```

### Restart Service
```bash
sudo systemctl restart earnapp-bot
```

### Stop Service
```bash
sudo systemctl stop earnapp-bot
```

## 🔄 Update Bot

```bash
cd /srv/earnapp_bot

# Backup konfigurasi
cp config.json config.json.backup
cp devices.json devices.json.backup

# Update code
git pull

# Restart service
sudo systemctl restart earnapp-bot
```

## 🗑️ Uninstall

### Uninstall via Bot (Recommended)
1. Buka bot di Telegram
2. Klik tombol "🗑️ Uninstall Bot"
3. Konfirmasi uninstall
4. Bot akan otomatis menghapus semua file

### Uninstall via Script
```bash
# Jalankan script uninstall lengkap
sudo bash /srv/earnapp_bot/uninstall.sh
```

### Uninstall Manual
```bash
# Stop service
sudo systemctl stop earnapp-bot
sudo systemctl disable earnapp-bot

# Hapus service file
sudo rm /etc/systemd/system/earnapp-bot.service

# Reload systemd
sudo systemctl daemon-reload

# Hapus direktori
sudo rm -rf /srv/earnapp_bot
```

## ✅ Verifikasi Instalasi

### 1. Cek Service Status
```bash
sudo systemctl status earnapp-bot
```
Harus menunjukkan `Active: active (running)`

### 2. Cek Log
```bash
journalctl -u earnapp-bot --no-pager -l
```
Harus menunjukkan "Bot EarnApp multi-device aktif..."

### 3. Test Bot di Telegram
1. Buka bot di Telegram
2. Kirim `/start`
3. Harus muncul menu pilihan device

### 4. Test Command
1. Pilih device
2. Klik "🟡 Status"
3. Harus menampilkan status EarnApp

## 🆘 Support

Jika ada masalah:
1. Cek log: `journalctl -u earnapp-bot -f`
2. Cek konfigurasi: `cat /srv/earnapp_bot/config.json`
3. Test manual: `cd /srv/earnapp_bot && source venv/bin/activate && python earnapp_bot.py`
4. Buat issue di GitHub dengan detail error
