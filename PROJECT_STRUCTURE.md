# Struktur Project EarnApp Bot

Dokumen ini menjelaskan struktur project setelah refactor bertahap. Tujuan utama refactor adalah memisahkan core application dari adapter Telegram dan Web UI tanpa mengganti cara menjalankan lama.

## Tree Ringkas

```text
earnapp_bot/
├── earnapp/                    # Package reusable hasil refactor
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       ├── errors.py           # Error dasar aplikasi
│       ├── executors.py        # Local/SSH/ADB executor seam
│       ├── models.py           # Model ringan untuk JSON legacy
│       ├── runtime.py          # Runtime path + EARNAPP_DATA_DIR
│       ├── storage.py          # JsonStorage, atomic write, locking
│       ├── use_cases.py        # Workflow shared bot dan Web UI
│       └── workers.py          # Background monitor/restart/schedule
├── docs/
│   ├── ARCHITECTURE.md         # Arsitektur target
│   └── REFACTOR_PLAN.md        # Plan refactor bertahap
├── webui/
│   ├── app.py                  # Flask adapter tipis
│   ├── install.sh
│   ├── run.sh
│   ├── uninstall.sh
│   ├── requirements.txt
│   ├── templates/
│   └── static/
├── earnapp_bot.py              # Telegram adapter / entry point lama
├── config.example.json
├── requirements.txt
├── install.sh
├── uninstall.sh
├── README.md
├── INSTALL.md
├── PROJECT_STRUCTURE.md
├── FEATURES.md
├── UNINSTALL_GUIDE.md
└── LICENSE
```

## Runtime JSON

File runtime berikut tidak dimaksudkan untuk di-commit karena berisi konfigurasi lokal dan data operasional:

- `config.json` - bot token dan Telegram admin ID.
- `devices.json` - daftar device SSH/ADB/local, termasuk kredensial SSH jika digunakan.
- `schedules.json` - jadwal time-based schedule.
- `auto_restart.json` - konfigurasi interval auto-restart.
- `activity_log.json` - log operasi start/stop/restart.

Semua akses runtime JSON sekarang melewati `earnapp.core.storage.JsonStorage`. Storage ini menyediakan default value, atomic write, dan lock file sederhana.

## Core Package

### `earnapp.core.runtime`

Menentukan lokasi file runtime. Default data directory adalah project root. Jika environment variable `EARNAPP_DATA_DIR` di-set, file runtime akan dibaca/ditulis dari directory tersebut.

### `earnapp.core.storage`

Satu seam untuk baca/tulis JSON runtime:

- config
- devices
- schedules
- auto-restart
- activity log

### `earnapp.core.models`

Model ringan untuk menjaga bentuk data legacy tetap jelas tanpa memaksa migrasi database.

### `earnapp.core.executors`

Memusatkan eksekusi command untuk:

- local device
- SSH device
- ADB wireless device

Telegram dan Web UI tidak perlu tahu detail `subprocess`, Paramiko, atau command ADB.

### `earnapp.core.use_cases`

Workflow shared untuk device CRUD, status, start/stop/restart, bulk operation, schedule, auto-restart, health-check, dan activity log.

### `earnapp.core.workers`

Background loop untuk monitoring, auto-restart, dan time schedule. Worker membaca ulang shared JSON secara berkala agar perubahan dari Web UI bisa terlihat tanpa restart bot pada operasi normal.

## Entry Point dan Adapter

### `earnapp_bot.py`

Masih menjadi entry point Telegram yang kompatibel dengan cara menjalankan lama:

```bash
python earnapp_bot.py
```

File ini sekarang bertindak sebagai adapter Telegram. Handler/menu tetap berada di file ini, tetapi workflow penting diarahkan ke `earnapp.core`.

### `webui/app.py`

Flask adapter untuk endpoint `/api/*`. File ini menambahkan project root ke `sys.path`, lalu memakai `earnapp.core.storage` dan `earnapp.core.use_cases`.

## Deployment

### Clone Repository

```bash
git clone https://github.com/latifangren/earnapp_bot.git
cd earnapp_bot
sudo bash install.sh
```

### Manual ke `/srv/earnapp_bot`

```bash
sudo mkdir -p /srv/earnapp_bot
cd /srv/earnapp_bot
sudo git clone https://github.com/latifangren/earnapp_bot.git .
sudo chown -R $USER:$USER /srv/earnapp_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Pastikan folder `earnapp/` ikut ada di `/srv/earnapp_bot`, karena bot dan Web UI mengimpor package tersebut.

## Runtime Data Directory

Default runtime directory adalah project root, misalnya `/srv/earnapp_bot`.

Jika ingin menyimpan JSON runtime di lokasi lain, set environment variable yang sama di service bot dan Web UI:

```ini
Environment=EARNAPP_DATA_DIR=/srv/earnapp_bot
```

Jika value berbeda antara bot dan Web UI, data tidak akan sinkron.

## Dependencies

### Python Packages

- `pyTelegramBotAPI` - Telegram Bot API.
- `paramiko` - SSH executor.
- Flask dependencies untuk Web UI berada di `webui/requirements.txt` jika Web UI diinstall mandiri.

### System Requirements

- Python 3.6+
- Ubuntu/Debian Linux
- SSH access untuk device SSH
- ADB untuk device Android/ADB wireless
- EarnApp terinstall di device target

## Security Notes

1. Jangan commit `config.json`, `devices.json`, atau runtime JSON lain.
2. `devices.json` bisa berisi password SSH; batasi permission file dan akses server.
3. Telegram bot hanya menerima admin ID yang dikonfigurasi.
4. Web UI belum memiliki autentikasi bawaan; lindungi dengan firewall/reverse proxy/auth jika production.
5. Gunakan SSH key jika memungkinkan.

## Monitoring

```bash
sudo systemctl status earnapp-bot
journalctl -u earnapp-bot -f
sudo systemctl restart earnapp-bot
```

Untuk Web UI:

```bash
sudo systemctl status earnapp-webui
journalctl -u earnapp-webui -f
```

## Development Checks

```bash
python3 -m py_compile earnapp_bot.py webui/app.py earnapp/core/*.py
bash -n install.sh uninstall.sh webui/install.sh webui/run.sh webui/uninstall.sh
```

Full runtime test Telegram/Web UI membutuhkan dependencies terinstall dan konfigurasi valid.

## Support

- GitHub Issues: https://github.com/latifangren/earnapp_bot/issues
- Dokumentasi utama: `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md`
- Log bot: `journalctl -u earnapp-bot -f`
