# 🔄 Informasi Sinkronisasi Web UI dengan Bot Telegram

## ✅ Data Tetap Sinkron!

Meskipun Web UI memiliki **instalasi mandiri** (venv dan systemd service sendiri), **semua data tetap sinkron** dengan bot Telegram karena menggunakan file JSON yang sama.

## 📁 File yang Di-share (Sinkron)

Semua file berikut berada di **root directory** (`/srv/earnapp_bot/`) dan digunakan oleh **kedua aplikasi**:

### 1. `devices.json`
- **Fungsi:** Daftar semua device (SSH, ADB, Local)
- **Sinkronisasi:** 
  - ✅ Tambah device via Web UI → Terlihat di Bot Telegram
  - ✅ Tambah device via Bot Telegram → Terlihat di Web UI
  - ✅ Hapus device via Web UI → Terlihat di Bot Telegram
  - ✅ Hapus device via Bot Telegram → Terlihat di Web UI

### 2. `schedules.json`
- **Fungsi:** Jadwal otomatis (time-based schedule)
- **Sinkronisasi:**
  - ✅ Buat jadwal reboot via Bot Telegram → Terlihat di Web UI
  - ✅ Buat jadwal via Web UI → Terlihat di Bot Telegram
  - ✅ Edit/Delete jadwal → Sinkron di kedua interface

### 3. `auto_restart.json`
- **Fungsi:** Konfigurasi auto restart interval
- **Sinkronisasi:**
  - ✅ Enable/Disable auto restart via Bot → Terlihat di Web UI
  - ✅ Set interval via Bot → Terlihat di Web UI
  - ✅ Perubahan via Web UI → Terlihat di Bot

### 4. `activity_log.json`
- **Fungsi:** Log semua operasi (start/stop/restart)
- **Sinkronisasi:**
  - ✅ Start device via Web UI → Ter-log, terlihat di Bot
  - ✅ Stop device via Bot → Ter-log, terlihat di Web UI
  - ✅ Auto restart → Ter-log di kedua interface

### 5. `config.json`
- **Fungsi:** Konfigurasi bot token dan admin ID
- **Sinkronisasi:** Shared untuk referensi logging

## 🔍 Cara Kerja Sinkronisasi

### Path File di Web UI:
```python
# webui/app.py
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ROOT_DIR = /srv/earnapp_bot

DEVICE_FILE = os.path.join(ROOT_DIR, "devices.json")
SCHEDULE_FILE = os.path.join(ROOT_DIR, "schedules.json")
AUTO_RESTART_FILE = os.path.join(ROOT_DIR, "auto_restart.json")
ACTIVITY_LOG_FILE = os.path.join(ROOT_DIR, "activity_log.json")
```

### Path File di Bot Telegram:
```python
# earnapp_bot.py
DEVICE_FILE = "devices.json"  # Di root directory
SCHEDULE_FILE = "schedules.json"  # Di root directory
# ... dst
```

**Kedua aplikasi membaca/menulis ke file yang sama!**

## 📊 Contoh Sinkronisasi Real-time

### Skenario 1: Tambah Device
1. User tambah device "Server1" via Bot Telegram
2. Bot menyimpan ke `devices.json`
3. Web UI refresh → Device "Server1" langsung muncul
4. User bisa langsung kontrol device via Web UI

### Skenario 2: Buat Jadwal Reboot
1. User buat jadwal reboot setiap hari jam 02:00 via Bot Telegram
2. Bot menyimpan ke `schedules.json`
3. Web UI refresh → Jadwal langsung terlihat di Web UI
4. Bot akan eksekusi jadwal sesuai schedule

### Skenario 3: Start Device
1. User start device "Server1" via Web UI
2. Web UI menyimpan log ke `activity_log.json`
3. Bot membaca log → Activity terlihat di bot
4. Status device update di kedua interface

## ⚙️ Instalasi Mandiri vs Sinkronisasi

### Yang Mandiri (Tidak Sinkron):
- ✅ **Virtual Environment** - `webui/venv/` (terpisah dari bot)
- ✅ **Systemd Service** - `earnapp-webui.service` (terpisah dari `earnapp-bot.service`)
- ✅ **Dependencies** - Flask dll di venv webui (tidak mengganggu bot)

### Yang Sinkron (Shared):
- ✅ **devices.json** - Shared
- ✅ **schedules.json** - Shared
- ✅ **auto_restart.json** - Shared
- ✅ **activity_log.json** - Shared
- ✅ **config.json** - Shared

## 🎯 Kesimpulan

**Web UI dan Bot Telegram:**
- ✅ **Data 100% sinkron** - Semua perubahan langsung terlihat
- ✅ **Instalasi mandiri** - Tidak mengganggu satu sama lain
- ✅ **Bisa berjalan bersamaan** - Tanpa konflik
- ✅ **Update independen** - Update Web UI tidak mempengaruhi bot

**Best Practice:**
- Gunakan Web UI untuk monitoring dan quick actions
- Gunakan Bot Telegram untuk automation dan notifications
- Keduanya saling melengkapi dengan data yang sinkron!

