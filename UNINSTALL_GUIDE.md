# 🗑️ Panduan Uninstall EarnApp Bot

## 🚀 Cara Uninstall

### 1. Uninstall via Bot (Recommended)
**Cara termudah dan paling aman:**

1. **Buka bot di Telegram**
2. **Klik tombol "🗑️ Uninstall Bot"**
3. **Konfirmasi uninstall** dengan klik "✅ Ya, Hapus Bot"
4. **Bot akan otomatis menghapus semua file**

### 2. Uninstall via Script
**Untuk uninstall lengkap dengan konfirmasi:**

```bash
# Jalankan script uninstall
sudo bash /srv/earnapp_bot/uninstall.sh
```

Script akan:
- ✅ Menghentikan service
- ✅ Menghapus service file
- ✅ Menghapus direktori bot
- ✅ Membersihkan log
- ✅ Menghapus file temporary
- ✅ Mencari dan menghapus file tersisa
- ✅ Membersihkan Python cache
- ✅ Mencari dan menghapus cron job
- ✅ Mencari dan menghapus alias/function

### 3. Uninstall Manual
**Untuk uninstall cepat:**

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

## 🔍 Fitur Uninstall Script

### Konfirmasi Uninstall
Script akan meminta konfirmasi sebelum menghapus:
- ✅ Konfirmasi uninstall utama
- ✅ Konfirmasi backup konfigurasi
- ✅ Konfirmasi hapus file tersisa
- ✅ Konfirmasi kill process
- ✅ Konfirmasi hapus cron job
- ✅ Konfirmasi hapus alias/function

### Backup Otomatis
Script menawarkan backup konfigurasi:
```bash
# Backup akan disimpan di:
/tmp/earnapp_bot_backup_YYYYMMDD_HHMMSS/
```

### Pembersihan Lengkap
Script akan membersihkan:
- ✅ Service systemd
- ✅ Direktori bot
- ✅ Log systemd
- ✅ Process yang berjalan
- ✅ File temporary
- ✅ Python cache
- ✅ File konfigurasi tersisa
- ✅ Cron job
- ✅ Alias/function di shell profile

## ⚠️ Peringatan

### Sebelum Uninstall
1. **Backup konfigurasi** jika diperlukan
2. **Stop semua device** yang sedang dikontrol
3. **Catat device SSH** yang sudah dikonfigurasi
4. **Pastikan tidak ada process penting** yang berjalan

### Setelah Uninstall
1. **Restart sistem** untuk memastikan bersih
2. **Cek log** jika ada masalah: `journalctl -u earnapp-bot`
3. **Hapus backup** jika tidak diperlukan: `rm -rf /tmp/earnapp_bot_backup_*`

## 🔧 Troubleshooting Uninstall

### Service Masih Aktif
```bash
# Cek status
sudo systemctl status earnapp-bot

# Force stop
sudo systemctl stop earnapp-bot
sudo systemctl disable earnapp-bot
```

### File Tidak Terhapus
```bash
# Cek permission
ls -la /srv/earnapp_bot

# Force delete
sudo rm -rf /srv/earnapp_bot
```

### Process Masih Berjalan
```bash
# Cari process
ps aux | grep earnapp_bot

# Kill process
sudo kill -9 $(pgrep -f earnapp_bot)
```

### Log Masih Ada
```bash
# Hapus log
sudo journalctl --vacuum-time=1s --unit=earnapp-bot
```

## ✅ Verifikasi Uninstall

### Cek Service
```bash
# Harus menunjukkan "inactive"
sudo systemctl status earnapp-bot
```

### Cek Direktori
```bash
# Harus menunjukkan "No such file or directory"
ls -la /srv/earnapp_bot
```

### Cek Process
```bash
# Harus kosong
ps aux | grep earnapp_bot
```

### Cek Log
```bash
# Harus kosong
journalctl -u earnapp-bot --no-pager
```

## 🔄 Reinstall

Jika ingin install ulang:

```bash
# Clone repository
git clone https://github.com/username/earnapp_bot.git
cd earnapp_bot

# Install
sudo bash install.sh

# Konfigurasi
sudo nano /srv/earnapp_bot/config.json

# Start
sudo systemctl start earnapp-bot
```

## 📞 Support

Jika ada masalah saat uninstall:

1. **Cek log**: `journalctl -u earnapp-bot -f`
2. **Cek permission**: `ls -la /srv/earnapp_bot`
3. **Cek process**: `ps aux | grep earnapp_bot`
4. **Buat issue** di GitHub dengan detail error

---

**💡 Tips**: Gunakan uninstall via bot untuk kemudahan, atau script uninstall untuk kontrol penuh.
