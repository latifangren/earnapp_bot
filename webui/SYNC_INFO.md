# Informasi Sinkronisasi Web UI dengan Bot Telegram

Web UI dan Bot Telegram berbagi runtime JSON yang sama melalui `earnapp.core.storage.JsonStorage`.

## File yang Di-share

File berikut berada di data directory yang sama, default-nya root project `/srv/earnapp_bot`:

- `config.json` - konfigurasi bot token dan admin ID.
- `devices.json` - daftar device SSH/ADB/local.
- `schedules.json` - time-based schedule.
- `auto_restart.json` - konfigurasi auto-restart interval.
- `activity_log.json` - log operasi.

Jika `EARNAPP_DATA_DIR` di-set, kedua service harus memakai value yang sama.

## Cara Kerja Setelah Refactor

### Web UI

`webui/app.py` adalah adapter Flask. Semua route API memanggil use-case dari `earnapp.core.use_cases`, lalu use-case membaca/menulis runtime JSON melalui `JsonStorage`.

### Bot Telegram

`earnapp_bot.py` adalah adapter Telegram. Handler membaca ulang state runtime sebelum operasi penting seperti list device, schedule, auto-restart, dan activity log.

### Worker Bot

Worker auto-restart dan time-schedule di `earnapp.core.workers` membaca ulang `auto_restart.json` dan `schedules.json` pada setiap loop. Dengan begitu, perubahan dari Web UI normalnya terlihat tanpa restart bot.

## Proteksi Write

`JsonStorage` memakai:

- default value saat file belum ada,
- atomic write via temporary file dan replace,
- lock file sederhana untuk koordinasi antar proses.

Ini mengurangi risiko file JSON rusak saat Bot dan Web UI berjalan bersamaan.

## Contoh Sinkronisasi

### Tambah Device dari Web UI

1. Web UI menyimpan device ke `devices.json` melalui `JsonStorage`.
2. Bot refresh `devices` saat menu/pilihan device dibuka.
3. Device baru muncul di Telegram tanpa restart bot pada operasi normal.

### Buat Schedule dari Web UI

1. Web UI menyimpan schedule ke `schedules.json`.
2. Worker schedule membaca ulang `schedules.json` pada loop berikutnya.
3. Schedule baru bisa dieksekusi tanpa restart bot.

### Set Auto-Restart dari Web UI

1. Web UI menyimpan policy ke `auto_restart.json`.
2. Worker auto-restart membaca ulang policy pada loop berikutnya.
3. Policy baru dipakai tanpa restart bot.

### Activity Log

1. Operasi dari Web UI atau Bot menulis ke `activity_log.json`.
2. Tampilan log di kedua interface membaca ulang file saat dibuka.

## Batasan Sinkronisasi

Sinkronisasi ini berbasis file JSON, bukan database transaksi. Jika Bot dan Web UI mengubah key yang sama pada waktu yang sangat bersamaan, write terakhir masih bisa menang.

Untuk penggunaan normal, pola refresh-before-mutate dan storage lock sudah cukup menjaga data tetap sinkron. Jika concurrency makin tinggi, langkah berikutnya adalah mengganti storage adapter ke SQLite/Postgres tanpa mengubah adapter Telegram/Web UI secara besar.

## Checklist Jika Data Tidak Sinkron

1. Pastikan kedua service berjalan dari deployment yang sama.
2. Pastikan folder `earnapp/` ada di root project.
3. Cek apakah `EARNAPP_DATA_DIR` berbeda antara service bot dan Web UI.
4. Restart service jika baru mengganti environment variable.
5. Cek permission file JSON di data directory.

Contoh cek service:

```bash
sudo systemctl status earnapp-bot
sudo systemctl status earnapp-webui
journalctl -u earnapp-bot -f
journalctl -u earnapp-webui -f
```
