# 🌐 EarnApp Bot - Web UI

Web interface untuk mengontrol EarnApp di multiple device secara remote melalui SSH atau ADB.

**✅ Data tetap sinkron dengan Bot Telegram!** Meskipun instalasi mandiri, semua data (devices, schedules, logs) tetap shared. Lihat [SYNC_INFO.md](SYNC_INFO.md) untuk detail sinkronisasi.

## ✨ Fitur

- 📊 **Dashboard Device** - Tampilkan semua device dengan status real-time
- 🟢 **Start/Stop/Restart** - Kontrol EarnApp di setiap device
- 🚀 **Bulk Operations** - Start/stop semua device sekaligus
- ➕ **Add Device** - Tambah device baru (SSH, ADB, atau Local)
- 🗑️ **Delete Device** - Hapus device dari konfigurasi
- 📝 **Activity Logs** - Lihat history operasi dengan filter per device
- 🔄 **Auto Refresh** - Auto refresh status setiap 30 detik
- 📱 **Responsive Design** - Dapat diakses dari desktop dan mobile

## 🚀 Instalasi

### Opsi 1: Instalasi Mandiri (Recommended)

Web UI dapat diinstall secara mandiri tanpa mengganggu bot Telegram:
di directori /srv/earnapp_bot 
```bash
# folder webui/ beserta isinya sudah ada di dalam
# Masuk ke direktori webui
cd webui
chmod +x install.sh
# Jalankan script instalasi
sudo bash install.sh
```

Script ini akan:
- Membuat virtual environment di dalam folder `webui/venv`
- Install semua dependencies (termasuk Flask)
- Membuat systemd service `earnapp-webui`
- Setup konfigurasi otomatis

**Setelah instalasi:**
```bash
# Start Web UI service
sudo systemctl start earnapp-webui

# Cek status
sudo systemctl status earnapp-webui

# Enable auto-start on boot
sudo systemctl enable earnapp-webui
```

### 2. Konfigurasi

Pastikan file `config.json` sudah ada di root directory proyek:

```json
{
  "bot_token": "YOUR_BOT_TOKEN_HERE",
  "admin_telegram_id": "YOUR_TELEGRAM_ID_HERE"
}
```

**Catatan:** Web UI tidak memerlukan bot token, tapi admin_telegram_id digunakan untuk referensi logging.

### 3. Jalankan Web UI

**Cara 1 - Menggunakan Systemd Service (Recommended untuk Production):**
```bash
# Start service
sudo systemctl start earnapp-webui

# Cek status
sudo systemctl status earnapp-webui

# Stop service
sudo systemctl stop earnapp-webui

# Enable auto-start on boot
sudo systemctl enable earnapp-webui

# Lihat log
journalctl -u earnapp-webui -f
```

**Cara 2 - Menggunakan script run.sh (Development):**
```bash
# dari dalam direktori webui
cd webui
chmod +x run.sh
bash run.sh
```

Web UI akan berjalan di `http://localhost:5000`

**Catatan:** 
- **Instalasi Mandiri**: Web UI memiliki venv sendiri di `webui/venv/`, tidak terganggu dengan bot Telegram

- Disarankan menggunakan systemd service untuk production

### 4. Akses Web UI

Buka browser dan akses:
- **Local:** http://localhost:5000
- **Network:** http://YOUR_SERVER_IP:5000

## 🔧 Konfigurasi Port

Untuk mengubah port, edit file `webui/app.py` di bagian akhir:

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

Ubah `port=5000` ke port yang diinginkan.

## 📁 Struktur File

```
webui/
├── app.py              # Flask backend
├── install.sh          # Script instalasi mandiri
├── uninstall.sh        # Script uninstall
├── run.sh              # Script untuk menjalankan Web UI
├── requirements.txt    # Dependencies Web UI (opsional)
├── venv/               # Virtual environment (setelah install)
├── templates/
│   └── index.html     # Frontend HTML
├── static/
│   ├── css/
│   │   └── style.css  # CSS styling
│   └── js/
│       └── app.js     # JavaScript frontend
└── README.md          # Dokumentasi ini
```

## 🔐 Keamanan

**PENTING:** Web UI saat ini tidak memiliki autentikasi. Untuk penggunaan production, disarankan untuk:

1. Menambahkan autentikasi (login/password)
2. Menggunakan HTTPS
3. Membatasi akses dengan firewall
4. Menambahkan rate limiting

## 🐛 Troubleshooting

### Port Already in Use

Jika port 5000 sudah digunakan:

```bash
# Cek proses yang menggunakan port
netstat -ano | findstr :5000

# Atau ubah port di app.py
```

### Device Tidak Muncul

Pastikan file `devices.json` ada di root directory proyek (bukan di folder webui).

### Error SSH/ADB Connection

- Pastikan kredensial SSH benar
- Pastikan device ADB sudah di-connect via wireless
- Cek firewall dan network connectivity

## 🔄 Integrasi dengan Telegram Bot

**✅ Web UI TETAP SINKRON dengan Bot Telegram!**

Meskipun Web UI memiliki instalasi mandiri (venv dan systemd service sendiri), **data tetap shared** dengan bot Telegram karena menggunakan file JSON yang sama di root directory:

### File yang Di-share (Sinkron):
- ✅ `devices.json` - Daftar device (tambah/hapus device)
- ✅ `schedules.json` - Jadwal otomatis (time-based schedule)
- ✅ `auto_restart.json` - Konfigurasi auto restart interval
- ✅ `activity_log.json` - Log aktivitas (semua operasi)

### Contoh Sinkronisasi:
1. **Jadwal Reboot via Bot Telegram** → Langsung terlihat di Web UI
2. **Tambah Device via Web UI** → Langsung terlihat di Bot Telegram
3. **Start/Stop Device via Web UI** → Ter-log di activity_log.json, terlihat di bot
4. **Auto Restart Settings via Bot** → Langsung terlihat di Web UI

### Keuntungan Instalasi Mandiri:
- ✅ **Venv terpisah** - Tidak konflik dependencies
- ✅ **Systemd service terpisah** - Bisa restart Web UI tanpa restart bot
- ✅ **Update independen** - Update Web UI tidak mempengaruhi bot
- ✅ **Data tetap shared** - Tetap sinkron dengan bot Telegram

**Catatan:** Semua file JSON berada di root directory (`/srv/earnapp_bot/`), bukan di folder `webui/`. Ini memastikan sinkronisasi penuh antara Web UI dan Bot Telegram.

## 📝 API Endpoints

Web UI menyediakan REST API yang dapat digunakan untuk integrasi:

- `GET /api/devices` - Dapatkan semua device
- `POST /api/devices` - Tambah device baru
- `DELETE /api/devices/<name>` - Hapus device
- `GET /api/devices/<name>/status` - Status device
- `GET /api/devices/all/status` - Status semua device
- `POST /api/devices/<name>/start` - Start device
- `POST /api/devices/<name>/stop` - Stop device
- `POST /api/devices/<name>/restart` - Restart device
- `POST /api/devices/all/start` - Start semua device
- `POST /api/devices/all/stop` - Stop semua device
- `GET /api/devices/<name>/id` - Dapatkan device ID
- `GET /api/activity-logs` - Dapatkan activity logs
- `GET /api/schedules` - Dapatkan schedules
- `GET /api/auto-restart` - Dapatkan auto restart settings

## 🚀 Production Deployment

### Menggunakan Systemd Service (Recommended)

Jika sudah install menggunakan `install.sh`, systemd service sudah dibuat otomatis:

```bash
# Start service
sudo systemctl start earnapp-webui

# Enable auto-start
sudo systemctl enable earnapp-webui

# Cek status
sudo systemctl status earnapp-webui

# Lihat log
journalctl -u earnapp-webui -f
```


## 📄 License

MIT License - sama dengan proyek utama

