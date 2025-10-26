# 🚀 Fitur EarnApp Bot

## 📊 Dashboard Multi-Device

### Deskripsi
Tampilkan status semua device sekaligus dalam satu tampilan yang mudah dibaca.

### Cara Menggunakan
1. Klik tombol **"📊 Dashboard"** di menu utama
2. Bot akan mengumpulkan data dari semua device
3. Tampilkan status kesehatan dan EarnApp untuk setiap device

### Format Tampilan
```
📊 DASHBOARD MULTI-DEVICE

🟢 🟢 Local
Status EarnApp running...

🔴 🔴 Server1
SSH error: Connection timeout
```

### Ikon Status
- 🟢 = Online/Healthy
- 🔴 = Offline/Error

---

## 🚀 Bulk Operations

### Start All Devices
Menjalankan EarnApp di semua device sekaligus.

**Cara Menggunakan:**
1. Klik tombol **"🚀 Start All"**
2. Bot akan menjalankan `earnapp start` di semua device
3. Tampilkan hasil untuk setiap device

### Stop All Devices
Menghentikan EarnApp di semua device sekaligus.

**Cara Menggunakan:**
1. Klik tombol **"🛑 Stop All"**
2. Konfirmasi dengan **"✅ Ya, Stop All"**
3. Bot akan menjalankan `earnapp stop` di semua device

### Format Hasil
```
🚀 START ALL DEVICES

Local: EarnApp started successfully
Server1: EarnApp started successfully
Server2: SSH error: Connection failed
```

---

## 🔍 Device Health Check

### Deskripsi
Cek kesehatan semua device untuk memastikan koneksi dan status.

### Cara Menggunakan
1. Klik tombol **"🔍 Health Check"**
2. Bot akan test koneksi ke setiap device
3. Tampilkan status online/offline dengan detail error

### Format Hasil
```
🔍 HEALTH CHECK RESULTS

🟢 Local: Online
🔴 Server1: Offline - SSH error: Connection timeout
🟢 Server2: Online
```

### Informasi yang Ditampilkan
- Status koneksi (Online/Offline)
- Error message jika ada masalah
- Timestamp last check

---

## ⏰ Scheduled Tasks

### Deskripsi
Jadwal otomatis untuk start/stop device (akan tersedia dalam update berikutnya).

### Menu Schedule
- **➕ Add Schedule** - Tambah jadwal baru
- **📋 List Schedule** - Lihat daftar jadwal
- **🗑️ Delete Schedule** - Hapus jadwal
- **⚙️ Settings** - Pengaturan schedule

### Status
🔄 **Dalam Pengembangan** - Fitur ini akan tersedia dalam update berikutnya.

---

## 🔔 Alert Notifications

### Deskripsi
Notifikasi otomatis via bot jika ada masalah dengan device.

### Jenis Alert
- **Device Offline** - Device tidak bisa diakses
- **Connection Error** - Error koneksi SSH
- **EarnApp Error** - Error pada EarnApp

### Pengaturan Alert
- **Alert Enabled**: ✅/❌
- **Check Interval**: 60 detik
- **Offline Threshold**: 300 detik (5 menit)

### Cara Kerja
1. Bot mengecek kesehatan device setiap 60 detik
2. Jika device offline > 5 menit, kirim alert ke admin
3. Alert dikirim via Telegram ke admin ID

### Format Alert
```
🚨 ALERT

Device 'Server1' offline selama 6 menit
```

---

## 🎯 Fitur Utama

### 1. Multi-Device Support
- Kontrol multiple device via SSH
- Device lokal dan remote
- Konfigurasi per device

### 2. Real-time Monitoring
- Dashboard real-time
- Health check otomatis
- Alert system

### 3. Bulk Operations
- Start/stop semua device
- Operasi massal
- Konfirmasi untuk operasi berbahaya

### 4. Admin Security
- Hanya admin yang bisa akses
- Konfirmasi untuk operasi penting
- Log aktivitas

### 5. User-friendly Interface
- Menu tombol yang mudah
- Konfirmasi inline
- Format pesan yang jelas

---

## 🔧 Penggunaan Lanjutan

### Command Line
```bash
# Start bot
python earnapp_bot.py

# Cek log
journalctl -u earnapp-bot -f

# Restart bot
sudo systemctl restart earnapp-bot
```

### Konfigurasi Alert
Edit `alert_settings` di `earnapp_bot.py`:
```python
alert_settings = {
    "enabled": True,
    "offline_threshold": 300,  # 5 menit
    "check_interval": 60  # 1 menit
}
```

### Menambah Device
1. Klik **"/adddevice"**
2. Masukkan IP address
3. Masukkan nama device
4. Masukkan username SSH
5. Masukkan password SSH

---

## 🚨 Troubleshooting

### Dashboard Tidak Menampilkan Data
- Cek koneksi ke device
- Pastikan EarnApp terinstall
- Cek log bot

### Alert Tidak Berfungsi
- Pastikan `alert_settings["enabled"] = True`
- Cek admin ID di config.json
- Cek log background monitor

### Bulk Operations Gagal
- Cek koneksi SSH ke semua device
- Pastikan username/password benar
- Cek firewall dan network

### Health Check Error
- Test koneksi manual: `ssh user@ip`
- Cek SSH service di device target
- Cek permission dan credential

---

## 📈 Performance

### Monitoring Interval
- Health check: Setiap 60 detik
- Alert check: Setiap 60 detik
- Dashboard: Real-time saat diminta

### Resource Usage
- CPU: Minimal (background thread)
- Memory: ~10-20MB
- Network: SSH connection per device

### Scalability
- Support hingga 50+ device
- Background monitoring efisien
- Error handling robust

---

## 🔄 Update Roadmap

### v1.1.0 (Coming Soon)
- ✅ Scheduled Tasks lengkap
- ✅ Device grouping
- ✅ Custom commands
- ✅ Advanced reporting

### v1.2.0 (Future)
- ✅ Web dashboard
- ✅ API endpoints
- ✅ Mobile app
- ✅ Cloud sync

---

**💡 Tips**: Gunakan Dashboard untuk monitoring cepat, Bulk Operations untuk efisiensi, dan Health Check untuk troubleshooting.
