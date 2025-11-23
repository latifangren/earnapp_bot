# 🤖 EarnApp Bot - Multi Device Controller

Bot Telegram untuk mengontrol EarnApp di multiple device secara remote melalui SSH atau lokal.

## ✨ Fitur

### 🎮 Kontrol Dasar
- 🟢 **Start/Stop EarnApp** - Kontrol EarnApp di device remote
- 📊 **Status Monitoring** - Cek status EarnApp real-time
- 📱 **Device Registration** - Register device baru ke EarnApp
- 🆔 **Show Device ID** - Tampilkan ID device EarnApp
- 💣 **Uninstall** - Hapus EarnApp dari device
- 🔄 **Ganti Device** - Pilih device lain dengan mudah

### 📊 Multi-Device Management
- 📊 **Dashboard Multi-Device** - Tampilkan status semua device sekaligus
- 🚀 **Bulk Operations** - Start/stop semua device sekaligus
- 🔍 **Device Health Check** - Cek kesehatan device secara berkala
- 🔄 **Multi Device Support** - Kontrol multiple device via SSH
- 📱 **Easy Device Management** - Tambah/hapus device via bot

### ⏰ Scheduled & Automation
- 🔄 **Auto Restart (Interval)** - Auto restart EarnApp setiap beberapa jam (stop → wait → start)
- 🕐 **Time-based Schedule** - Jadwal start/stop/restart pada waktu tertentu
- 📅 **Schedule Management** - Multiple schedule per device, support harian/mingguan
- ⚡ **Quick Actions** - Quick restart, quick status, enable/disable auto restart all

### 📝 Logging & History
- 📝 **Activity Log** - Log semua operasi (start/stop/restart)
- 🔍 **Filter Log** - Filter berdasarkan device atau tanggal
- 💾 **Export Log** - Export log ke file JSON/CSV
- 📊 **History per Device** - Lihat history operasi per device

### 🔔 Notifications
- 🔔 **Alert Notifications** - Notifikasi via bot jika device offline
- 📱 **Operation Notifications** - Notifikasi untuk setiap operasi (manual/auto/scheduled)
- ✅ **Bot Ready Notification** - Notifikasi setelah bot selesai restart

### 🔐 Security & Management
- 🔐 **Admin Only** - Hanya admin yang bisa akses bot
- 🗑️ **Uninstall Bot** - Hapus bot dari server (dengan konfirmasi)
- 🔄 **Restart Bot** - Restart bot dengan notifikasi ready

## 🚀 Instalasi Cepat

### 1. Clone Repository
```bash
git clone https://github.com/latifangren/earnapp_bot.git
cd earnapp_bot
```

### 2. Jalankan Script Instalasi
```bash
sudo bash install.sh
```

### 3. Konfigurasi Bot
Edit file `config.json`:
```json
{
  "bot_token": "YOUR_BOT_TOKEN_HERE",
  "admin_telegram_id": "YOUR_TELEGRAM_ID_HERE"
}
```

### 4. Start Bot

**Opsi 1 - Menggunakan Systemd (Recommended):**
```bash
sudo systemctl start earnapp-bot
sudo systemctl status earnapp-bot
```

**Opsi 2 - Menggunakan Nohup (tanpa systemd):**
```bash
cd /srv/earnapp_bot
nohup ./run_bot.sh > bot.log 2>&1 &
```

**Opsi 3 - Menggunakan Screen (tanpa systemd):**
```bash
screen -S earnapp_bot
cd /srv/earnapp_bot && ./run_bot.sh
# Tekan Ctrl+A lalu D untuk detach
```

⚠️ **PENTING**: Fitur auto restart dan time-based schedule menggunakan background threads yang hanya berjalan jika bot Python aktif. Systemd service memastikan bot selalu berjalan dan fitur auto tetap berfungsi.

## 📋 Prerequisites

### Server Requirements
- Ubuntu/Debian Linux
- Python 3.6+
- SSH access ke device target
- EarnApp terinstall di device target

### Telegram Setup
1. Buat bot baru via [@BotFather](https://t.me/botfather)
2. Dapatkan bot token
3. Dapatkan Telegram ID Anda via [@userinfobot](https://t.me/userinfobot)

## 🔧 Instalasi Manual

### 1. Install Dependencies
```bash
# Update sistem
sudo apt update && sudo apt upgrade -y

# Install Python dan dependencies
sudo apt install -y python3 python3-pip python3-venv libffi-dev libssl-dev

# Buat direktori
sudo mkdir -p /srv/earnapp_bot
cd /srv/earnapp_bot

# Clone repository
sudo git clone https://github.com/latifangren/earnapp_bot.git

# Buat virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### 2. Setup Konfigurasi
```bash
# Buat file konfigurasi
sudo nano config.json
```

Isi dengan:
```json
{
  "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
  "admin_telegram_id": "123456789"
}
```

### 3. Setup Systemd Service
```bash
# Buat service file
sudo nano /etc/systemd/system/earnapp-bot.service
```

Isi dengan:
```ini
[Unit]
Description=EarnApp Bot Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/srv/earnapp_bot
Environment=PATH=/srv/earnapp_bot/venv/bin:/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin
ExecStart=/srv/earnapp_bot/venv/bin/python earnapp_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Enable dan Start Service
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

## 📱 Cara Menggunakan

### 1. Start Bot
Kirim `/start` ke bot di Telegram

### 2. Pilih Device
Pilih device yang ingin dikontrol dari menu

### 3. Kontrol EarnApp
Gunakan tombol menu untuk:
- 🟢 **Start EarnApp** - Jalankan EarnApp
- 🔴 **Stop EarnApp** - Hentikan EarnApp
- 🟡 **Status** - Cek status EarnApp
- 📱 **Register** - Register device ke EarnApp
- 🆔 **Show ID** - Tampilkan Device ID
- 💣 **Uninstall** - Hapus EarnApp
- 🗑️ **Uninstall Bot** - Hapus bot dari server
- 📊 **Dashboard** - Tampilkan status semua device
- 🚀 **Start All** - Start EarnApp di semua device
- 🛑 **Stop All** - Stop EarnApp di semua device
- 🔍 **Health Check** - Cek kesehatan semua device
- ⏰ **Schedule** - Kelola jadwal otomatis (auto restart & time-based)
- ⚡ **Quick Actions** - Quick restart, quick status, enable/disable auto restart
- 📝 **Activity Log** - Lihat history dan export log
- 🔄 **Ganti Device** - Pilih device lain
- **/adddevice** - Tambah device baru

### 4. Tambah Device Baru
1. Kirim `/adddevice`
2. Masukkan IP address device
3. Masukkan nama device
4. Masukkan username SSH
5. Masukkan password SSH

### 5. Fitur Lengkap

#### 📊 Dashboard Multi-Device
- Tampilkan status semua device sekaligus
- Monitoring real-time kesehatan device
- Status EarnApp untuk setiap device

#### 🚀 Bulk Operations
- **Start All**: Jalankan EarnApp di semua device
- **Stop All**: Hentikan EarnApp di semua device (dengan konfirmasi)

#### 🔍 Device Health Check
- Cek koneksi ke semua device
- Tampilkan status online/offline
- Detail error jika ada masalah

#### 🔄 Auto Restart (Interval-based)
- Auto restart EarnApp setiap beberapa jam
- Konfigurasi interval per device (minimal 0.5 jam, maksimal 168 jam)
- Selalu jalankan: stop → wait 5 detik → start
- Notifikasi otomatis setiap kali dijalankan

#### 🕐 Time-based Schedule
- Jadwal start/stop/restart pada waktu tertentu (format HH:MM)
- Support multiple schedule per device
- Pilihan hari: setiap hari, hari kerja, weekend, atau manual
- Notifikasi otomatis saat schedule dieksekusi

#### ⚡ Quick Actions
- **Quick Restart**: Restart device (stop → wait → start) dalam 1 klik
- **Quick Status**: Cek status semua device sekaligus
- **Enable/Disable Auto Restart All**: Kontrol auto restart semua device

#### 📝 Activity Log & History
- Log semua operasi (start/stop/restart) dengan detail
- Filter log berdasarkan device atau tanggal
- Export log ke file JSON dan CSV
- History per device dengan detail timestamp
- Support filter: today, yesterday, week, atau tanggal spesifik

#### 🔔 Notifications
- **Operation Notifications**: Notifikasi untuk setiap operasi (manual/auto/scheduled)
- **Alert Notifications**: Notifikasi jika device offline lebih dari threshold
- **Bot Ready Notification**: Notifikasi setelah bot selesai restart
- Semua notifikasi dikirim ke admin Telegram

## 📁 Struktur File

```
earnapp_bot/
├── earnapp_bot.py          # Script utama bot
├── config.json             # Konfigurasi bot token & admin ID
├── devices.json            # Database device SSH
├── auto_restart.json       # Konfigurasi auto restart interval
├── schedules.json          # Konfigurasi time-based schedule
├── activity_log.json       # Log semua operasi
├── requirements.txt        # Dependencies Python
├── install.sh             # Script instalasi otomatis
├── uninstall.sh           # Script uninstall lengkap
├── run_bot.sh             # Script alternatif (tanpa systemd)
├── README.md              # Dokumentasi utama
├── FEATURES.md            # Dokumentasi fitur lengkap
└── INSTALL.md             # Panduan instalasi detail
```

## 🔐 Keamanan

- Bot hanya bisa diakses oleh admin yang terdaftar
- Konfigurasi sensitif disimpan di file terpisah
- SSH connection menggunakan timeout
- Error handling untuk mencegah crash

## 🐛 Troubleshooting

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
- Pastikan SSH service aktif di device target
- Cek username/password SSH
- Test koneksi manual: `ssh user@ip`

### EarnApp Command Error
- Pastikan EarnApp terinstall di device target
- Cek path EarnApp: `which earnapp`
- Test command manual: `earnapp status`

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

## 🔄 Update

```bash
cd /srv/earnapp_bot
git pull
sudo systemctl restart earnapp-bot
```

## 🗑️ Uninstall

### Uninstall via Bot (Recommended)
1. Buka bot di Telegram
2. Klik tombol "🗑️ Uninstall Bot"
3. Konfirmasi uninstall
4. Bot akan otomatis menghapus semua file

### Uninstall Manual
```bash
# Jalankan script uninstall
sudo bash /srv/earnapp_bot/uninstall.sh

# Atau uninstall manual
sudo systemctl stop earnapp-bot
sudo systemctl disable earnapp-bot
sudo rm /etc/systemd/system/earnapp-bot.service
sudo rm -rf /srv/earnapp_bot
sudo systemctl daemon-reload
```

## 📝 Changelog

### v1.2.0 (Latest)
- ✅ **Auto Restart (Interval)** - Auto restart EarnApp setiap beberapa jam
- ✅ **Time-based Schedule** - Jadwal start/stop/restart pada waktu tertentu
- ✅ **Quick Actions** - Quick restart, quick status, enable/disable auto restart all
- ✅ **Activity Log & History** - Logging semua operasi dengan filter dan export
- ✅ **Enhanced Notifications** - Notifikasi untuk semua operasi (manual/auto/scheduled)
- ✅ **Bot Ready Notification** - Notifikasi setelah bot selesai restart
- ✅ **Multiple Schedule Support** - Multiple schedule per device dengan pilihan hari
- ✅ **Export Log** - Export activity log ke JSON dan CSV

### v1.1.0
- ✅ Dashboard Multi-Device - Tampilkan status semua device sekaligus
- ✅ Bulk Operations - Start/stop semua device sekaligus
- ✅ Device Health Check - Cek kesehatan device secara berkala
- ✅ Alert Notifications - Notifikasi via bot jika ada masalah
- ✅ Background Monitoring - Monitoring otomatis dengan thread
- ✅ Enhanced Menu - Menu yang lebih terorganisir
- ✅ Confirmation Dialogs - Konfirmasi untuk operasi penting

### v1.0.0
- ✅ Multi device support via SSH
- ✅ Admin authentication
- ✅ Easy device management
- ✅ Systemd service integration
- ✅ Error handling & logging

## 🤝 Contributing

1. Fork repository
2. Buat feature branch
3. Commit changes
4. Push ke branch
5. Buat Pull Request

## 📄 License

MIT License - lihat file [LICENSE](LICENSE) untuk detail

## 🆘 Support

Jika ada masalah atau pertanyaan:
1. Cek [Issues](https://github.com/latifangren/earnapp_bot/issues)
2. Buat issue baru dengan detail error
3. Sertakan log error dari `journalctl -u earnapp-bot`

---

**⚠️ Disclaimer**: Bot ini untuk keperluan pribadi. Pastikan Anda memiliki izin untuk mengakses device target.
