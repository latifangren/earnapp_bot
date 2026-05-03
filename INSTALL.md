# Panduan Instalasi EarnApp Bot

Dokumen ini menjelaskan instalasi EarnApp Bot setelah refactor bertahap. Entry point lama tetap dipakai (`earnapp_bot.py` dan `webui/app.py`), tetapi logic utama sekarang berada di package `earnapp/`.

## Instalasi Cepat

### 1. Persiapan Server

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-pip python3-venv libffi-dev libssl-dev
```

### 2. Clone Repository

```bash
git clone https://github.com/latifangren/earnapp_bot.git
cd earnapp_bot
sudo bash install.sh
```

Script installer akan menyalin komponen utama ke `/srv/earnapp_bot`, termasuk:

- `earnapp_bot.py`
- package `earnapp/`
- folder `docs/`
- folder `webui/` beserta template/static/script pendukung
- file `.md`, `.sh`, `requirements.txt`, dan `config.example.json`

### 3. Konfigurasi Bot

```bash
sudo nano /srv/earnapp_bot/config.json
```

Isi dengan token dan Telegram ID admin:

```json
{
  "bot_token": "YOUR_BOT_TOKEN_HERE",
  "admin_telegram_id": "YOUR_TELEGRAM_ID_HERE"
}
```

### 4. Start Bot

```bash
sudo systemctl start earnapp-bot
sudo systemctl enable earnapp-bot
sudo systemctl status earnapp-bot
```

## Instalasi Manual

### 1. Setup Direktori

```bash
sudo mkdir -p /srv/earnapp_bot
cd /srv/earnapp_bot
sudo git clone https://github.com/latifangren/earnapp_bot.git .
sudo chown -R $USER:$USER /srv/earnapp_bot
```

Pastikan folder `earnapp/` ikut ada setelah clone. Bot dan Web UI sekarang mengimpor modul dari `earnapp.core`, jadi package ini wajib ikut ter-deploy.

### 2. Setup Python Environment

```bash
cd /srv/earnapp_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Setup Konfigurasi

```bash
cp config.example.json config.json
nano config.json
```

Runtime JSON yang dipakai bersama:

- `config.json`
- `devices.json`
- `schedules.json`
- `auto_restart.json`
- `activity_log.json`

Secara default file-file ini dibaca dari project root (`/srv/earnapp_bot`). Jika ingin menyimpan data runtime di lokasi lain, set `EARNAPP_DATA_DIR` pada service bot dan Web UI ke path yang sama.

### 4. Setup Systemd Service

```bash
sudo nano /etc/systemd/system/earnapp-bot.service
```

Contoh service:

```ini
[Unit]
Description=EarnApp Bot Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/srv/earnapp_bot
Environment=PATH=/srv/earnapp_bot/venv/bin:/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin
# Optional jika runtime JSON disimpan di luar project root:
# Environment=EARNAPP_DATA_DIR=/srv/earnapp_bot
ExecStart=/srv/earnapp_bot/venv/bin/python earnapp_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Lalu aktifkan service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable earnapp-bot
sudo systemctl start earnapp-bot
sudo systemctl status earnapp-bot
```

## Runtime Data dan Sinkronisasi

Semua akses runtime JSON melewati `earnapp.core.storage.JsonStorage`. Storage ini menyediakan default value, atomic write, dan lock file sederhana supaya Bot Telegram dan Web UI tidak menulis file yang sama secara bersamaan tanpa koordinasi.

Jika Bot Telegram dan Web UI dijalankan sebagai service terpisah, pastikan keduanya memakai data directory yang sama:

```ini
Environment=EARNAPP_DATA_DIR=/srv/earnapp_bot
```

Jika environment variable tidak di-set, default-nya adalah project root tempat package `earnapp/` berada.

## Setup Telegram Bot

1. Buka [@BotFather](https://t.me/botfather).
2. Kirim `/newbot`.
3. Simpan Bot Token.
4. Buka [@userinfobot](https://t.me/userinfobot) untuk mendapatkan Telegram ID.
5. Masukkan keduanya ke `/srv/earnapp_bot/config.json`.

## Setup Device SSH

Install EarnApp di device target:

```bash
curl -sL https://earnapp.com/install.sh | sudo bash
```

Pastikan SSH aktif di device target:

```bash
sudo apt install -y openssh-server
sudo systemctl start ssh
sudo systemctl enable ssh
sudo systemctl status ssh
```

Tambah device melalui Telegram dengan `/adddevice` atau melalui Web UI.

## Setup Device ADB

Untuk device Android/ADB wireless, pastikan ADB tersedia di server dan device dapat diakses melalui IP/port yang benar. Port default adalah `5555`.

## Web UI

Installer utama menyalin folder `webui/` ke `/srv/earnapp_bot/webui`. Web UI dapat memakai virtual environment dan systemd service terpisah. Lihat `webui/README.md` untuk detail.

Jika Web UI dijalankan dari folder `webui/`, `webui/app.py` akan menambahkan project root ke `sys.path` agar package `earnapp/` tetap bisa diimpor.

Web UI sekarang fail-closed:

- Wajib set `WEBUI_AUTH_PASSWORD` atau route protected akan return `503`.
- Username default adalah `admin`; override dengan `WEBUI_AUTH_USERNAME` jika perlu.
- Bind default adalah `127.0.0.1:5000`; expose akses network hanya lewat reverse proxy/VPN/firewall yang aman.
- CORS default nonaktif; aktifkan hanya dengan `WEBUI_CORS_ORIGINS` berisi origin eksplisit.
- Frontend bawaan memakai token CSRF untuk request mutasi `/api/*`.

Installer Web UI mandiri (`webui/install.sh`) akan membuat password acak jika `WEBUI_AUTH_PASSWORD` belum disediakan, lalu menulisnya ke root-only env file `/etc/earnapp-webui.env` dengan permission `0600`. Service `earnapp-webui` membaca file tersebut lewat `EnvironmentFile`, sehingga password tidak ditulis langsung di unit systemd dan tidak dicetak ke output installer.

## Troubleshooting

### Bot Tidak Start

```bash
journalctl -u earnapp-bot -f
cat /srv/earnapp_bot/config.json
cd /srv/earnapp_bot
source venv/bin/activate
python earnapp_bot.py
```

### Import `earnapp` Gagal

Pastikan folder `/srv/earnapp_bot/earnapp/` ada. Jika tidak ada, deployment tidak lengkap atau installer lama dipakai.

### Data Web UI dan Bot Tidak Sama

Pastikan kedua service memakai project root/data directory yang sama. Jika memakai `EARNAPP_DATA_DIR`, set value yang sama di `earnapp-bot.service` dan `earnapp-webui.service`.

### SSH Connection Error

```bash
ssh user@ip_address
sudo systemctl status ssh
sudo ufw status
```

### EarnApp Command Error

```bash
which earnapp
earnapp status
ls -la /usr/bin/earnapp
```

### Permission Error

```bash
sudo chown -R $USER:$USER /srv/earnapp_bot
chmod +x /srv/earnapp_bot/earnapp_bot.py
```

## Monitoring

```bash
sudo systemctl status earnapp-bot
journalctl -u earnapp-bot -f
sudo systemctl restart earnapp-bot
sudo systemctl stop earnapp-bot
```

## Update Bot

```bash
cd /srv/earnapp_bot
cp config.json config.json.backup
cp devices.json devices.json.backup
cp schedules.json schedules.json.backup 2>/dev/null || true
cp auto_restart.json auto_restart.json.backup 2>/dev/null || true
cp activity_log.json activity_log.json.backup 2>/dev/null || true
git pull
sudo systemctl restart earnapp-bot
```

## Uninstall

### Via Bot

1. Buka bot di Telegram.
2. Klik tombol "Uninstall Bot".
3. Konfirmasi uninstall.

### Via Script

```bash
sudo bash /srv/earnapp_bot/uninstall.sh
```

### Manual

```bash
sudo systemctl stop earnapp-bot
sudo systemctl disable earnapp-bot
sudo rm /etc/systemd/system/earnapp-bot.service
sudo systemctl daemon-reload
sudo rm -rf /srv/earnapp_bot
```

## Verifikasi Instalasi

1. `sudo systemctl status earnapp-bot` menunjukkan service aktif.
2. `journalctl -u earnapp-bot --no-pager -l` menampilkan bot aktif.
3. Kirim `/start` ke bot Telegram.
4. Pilih device dan jalankan menu `Status`.

## Support

Jika ada masalah:

1. Cek log: `journalctl -u earnapp-bot -f`.
2. Cek konfigurasi: `cat /srv/earnapp_bot/config.json`.
3. Test manual: `cd /srv/earnapp_bot && source venv/bin/activate && python earnapp_bot.py`.
4. Buat issue di GitHub dengan detail error.
