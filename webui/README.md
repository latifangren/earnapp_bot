# EarnApp Bot - Web UI

Web interface untuk mengontrol EarnApp di multiple device melalui SSH, ADB wireless, atau local executor.

Data Web UI tetap shared dengan Bot Telegram melalui runtime JSON yang sama dan storage seam `earnapp.core.storage.JsonStorage`. Lihat [SYNC_INFO.md](SYNC_INFO.md) untuk detail sinkronisasi.

## Fitur

- Dashboard device dan status EarnApp.
- Start/stop/restart per device.
- Bulk start/stop semua device.
- Add/delete device SSH, ADB, atau local.
- Activity log dengan filter per device.
- Schedule dan auto-restart management.
- Health check semua device.
- Auto refresh status.
- Responsive UI.

## Cara Kerja Setelah Refactor

`webui/app.py` sekarang adalah Flask adapter tipis. Route HTTP hanya parse request dan memanggil use-case dari `earnapp.core.use_cases`.

Saat dijalankan dari folder `webui/`, file ini menambahkan project root ke `sys.path` agar package `earnapp/` bisa diimpor.

Komponen yang wajib ada di root project:

- `earnapp/`
- `webui/`
- runtime JSON (`config.json`, `devices.json`, `schedules.json`, `auto_restart.json`, `activity_log.json`)

## Instalasi

### Instalasi Mandiri Web UI

Jalankan dari `/srv/earnapp_bot/webui` setelah bot/project utama terpasang:

```bash
cd /srv/earnapp_bot/webui
chmod +x install.sh
sudo bash install.sh
```

Script ini akan:

- Membuat virtual environment di `webui/venv`.
- Install dependencies Web UI termasuk Flask.
- Membuat systemd service `earnapp-webui`.
- Mengisi `WEBUI_AUTH_PASSWORD` lewat root-only env file `/etc/earnapp-webui.env`. Jika env tersebut belum disediakan, installer membuat password acak dan menyimpan file dengan permission `0600`.
- Bind Web UI ke `127.0.0.1:5000` secara default.
- Menjalankan Web UI dari root project yang sama dengan bot.

Setelah instalasi:

```bash
sudo systemctl start earnapp-webui
sudo systemctl enable earnapp-webui
sudo systemctl status earnapp-webui
```

### Konfigurasi Runtime Data

Default runtime JSON berada di root project (`/srv/earnapp_bot`). Jika ingin memakai lokasi data lain, set `EARNAPP_DATA_DIR` pada service bot dan Web UI ke path yang sama.

Contoh systemd environment:

```ini
Environment=EARNAPP_DATA_DIR=/srv/earnapp_bot
```

Jika `EARNAPP_DATA_DIR` berbeda antara bot dan Web UI, keduanya akan membaca file runtime yang berbeda.

## Menjalankan Web UI

### Systemd

```bash
sudo systemctl start earnapp-webui
sudo systemctl status earnapp-webui
sudo systemctl stop earnapp-webui
journalctl -u earnapp-webui -f
```

### Development

```bash
cd /srv/earnapp_bot/webui
chmod +x run.sh
bash run.sh
```

Web UI berjalan di `http://127.0.0.1:5000` secara default.

## Akses Web UI

- Local: `http://127.0.0.1:5000`
- Network: expose only via reverse proxy/VPN, atau override `WEBUI_HOST` jika benar-benar diperlukan.

## Konfigurasi Akses dan Port

Web UI memakai Basic Auth browser-friendly untuk `/` dan semua `/api/*`.
Unsafe API request (`POST`, `PUT`, `PATCH`, `DELETE`) juga wajib mengirim header `X-CSRF-Token`. Frontend bawaan mengambil token dari meta tag halaman dan menambahkannya otomatis ke setiap request mutasi.

Wajib set password autentikasi lewat environment:

```bash
export WEBUI_AUTH_PASSWORD='ganti-password-ini'
```

Opsional:

- `WEBUI_AUTH_USERNAME` untuk mengganti username (default: `admin`).
- `WEBUI_HOST` untuk bind address (default: `127.0.0.1`).
- `WEBUI_PORT` untuk port (default: `5000`).
- `WEBUI_CORS_ORIGINS` untuk mengaktifkan CORS API secara eksplisit, isi daftar origin dipisah koma.

Jika `WEBUI_AUTH_PASSWORD` tidak di-set, request ke route protected akan ditolak dengan respons `503`.

Contoh systemd environment:

```ini
EnvironmentFile=/etc/earnapp-webui.env
```

Isi env file hanya boleh dibaca root/service admin:

```ini
WEBUI_AUTH_USERNAME=admin
WEBUI_AUTH_PASSWORD=ganti-password-ini
WEBUI_HOST=127.0.0.1
WEBUI_PORT=5000
```

Port dan bind default di `webui/app.py`:

```python
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=debug_mode)
```

Contoh expose aman via reverse proxy:

```bash
WEBUI_AUTH_PASSWORD='ganti-password-ini' \
WEBUI_HOST=127.0.0.1 \
WEBUI_PORT=5000 \
WEBUI_CORS_ORIGINS='https://dashboard.example.com' \
python3 app.py
```

## Struktur File

```text
webui/
├── app.py              # Flask adapter
├── install.sh          # Installer Web UI mandiri
├── uninstall.sh        # Uninstall Web UI
├── run.sh              # Runner development
├── requirements.txt    # Dependencies Web UI
├── templates/
│   └── index.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── README.md
└── SYNC_INFO.md
```

## Keamanan

PENTING:

1. Set `WEBUI_AUTH_PASSWORD` sebelum start Web UI.
2. Jangan bind ke `0.0.0.0` kecuali sudah di belakang reverse proxy/firewall yang aman.
3. CORS default nonaktif; aktifkan hanya lewat `WEBUI_CORS_ORIGINS` jika memang perlu.
4. Untuk client selain frontend bawaan, ambil CSRF token dari halaman `/` lalu kirim sebagai `X-CSRF-Token` pada request mutasi `/api/*`.
5. `GET /api/devices` sudah meredaksi field sensitif seperti `password`, `token`, `secret`, `private_key`, `passphrase`, dan `api_key`.

## Integrasi dengan Bot Telegram

Bot Telegram dan Web UI memakai file JSON yang sama melalui `JsonStorage`:

- `devices.json`
- `schedules.json`
- `auto_restart.json`
- `activity_log.json`
- `config.json`

Bot Telegram juga refresh state sebelum read/mutate, dan worker auto-restart/time-schedule membaca ulang JSON setiap loop. Perubahan dari Web UI normalnya terlihat tanpa restart bot.

Catatan: Jika Bot dan Web UI mengubah key yang sama pada waktu yang sangat bersamaan, write terakhir masih bisa menang. Untuk penggunaan normal, lock file dan refresh-before-mutate mengurangi risiko overwrite stale data.

## API Endpoints

Web UI menyediakan endpoint berikut:

- `GET /api/devices` - daftar semua device.
- `POST /api/devices` - tambah device.
- `DELETE /api/devices/<device_name>` - hapus device.
- `GET /api/devices/<device_name>/status` - status satu device.
- `GET /api/devices/all/status` - status semua device.
- `POST /api/devices/<device_name>/start` - start device.
- `POST /api/devices/<device_name>/stop` - stop device.
- `POST /api/devices/<device_name>/restart` - restart device.
- `POST /api/devices/all/restart` - restart semua device lewat shared core use-case.
- `POST /api/devices/all/start` - start semua device.
- `POST /api/devices/all/stop` - stop semua device.
- `POST /api/devices/all/health-check` - health check semua device.
- `GET /api/devices/<device_name>/id` - ambil device ID.
- `GET /api/activity-logs` - ambil activity logs.
- `GET /api/schedules` - ambil schedules.
- `POST /api/schedules` - tambah schedule.
- `DELETE /api/schedules/<task_id>` - hapus schedule.
- `GET /api/auto-restart` - ambil auto-restart settings.
- `POST /api/auto-restart/<device_name>` - set auto-restart untuk device.
- `DELETE /api/auto-restart/<device_name>` - disable auto-restart untuk device.

## Troubleshooting

### Import `earnapp` Gagal

Pastikan Web UI dijalankan dari deployment yang memiliki root project lengkap:

```bash
ls /srv/earnapp_bot/earnapp
ls /srv/earnapp_bot/webui
```

### Device Tidak Muncul

Pastikan Web UI dan bot memakai data directory yang sama. Cek `EARNAPP_DATA_DIR` di kedua service jika digunakan.

### Port Sudah Digunakan

```bash
ss -tlnp | grep 5000
```

Atau ubah port di `webui/app.py`.

### SSH/ADB Error

- Pastikan kredensial SSH benar.
- Pastikan ADB tersedia di server.
- Pastikan device bisa diakses dari server.
- Cek firewall dan network connectivity.

## Production Deployment

```bash
sudo systemctl start earnapp-webui
sudo systemctl enable earnapp-webui
sudo systemctl status earnapp-webui
journalctl -u earnapp-webui -f
```

## License

MIT License - sama dengan proyek utama.
