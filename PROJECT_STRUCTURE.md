# 📁 Struktur Project EarnApp Bot

## 🗂️ File dan Direktori

```
earnapp_bot/
├── 📄 earnapp_bot.py          # Script utama bot Telegram
├── ⚙️ config.json             # Konfigurasi bot token & admin ID (SENSITIVE)
├── 📱 devices.json            # Database device SSH (SENSITIVE)
├── 📋 requirements.txt        # Dependencies Python
├── 🚀 install.sh             # Script instalasi otomatis
├── 🗑️ uninstall.sh           # Script uninstall lengkap
├── 📖 README.md              # Dokumentasi utama
├── 📋 INSTALL.md             # Panduan instalasi detail
├── 📁 PROJECT_STRUCTURE.md   # Dokumentasi struktur project
├── ⚙️ config.example.json    # Template konfigurasi
├── 📄 LICENSE                # Lisensi MIT
└── 🔒 .gitignore             # File yang diabaikan Git
```

## 📄 Penjelasan File

### Core Files
- **`earnapp_bot.py`** - Script utama bot yang menangani semua fungsi
- **`config.json`** - Menyimpan bot token dan admin telegram ID (SENSITIVE)
- **`devices.json`** - Database device SSH dengan kredensial (SENSITIVE)

### Dependencies
- **`requirements.txt`** - Daftar package Python yang diperlukan
- **`install.sh`** - Script bash untuk instalasi otomatis
- **`uninstall.sh`** - Script bash untuk uninstall lengkap

### Documentation
- **`README.md`** - Dokumentasi utama dengan fitur dan cara penggunaan
- **`INSTALL.md`** - Panduan instalasi step-by-step yang detail
- **`PROJECT_STRUCTURE.md`** - Dokumentasi struktur project ini

### Configuration
- **`config.example.json`** - Template konfigurasi untuk user baru
- **`.gitignore`** - File yang tidak di-commit ke Git (konfigurasi sensitif)

### Legal
- **`LICENSE`** - Lisensi MIT untuk project

## 🔐 File Sensitif

File berikut **TIDAK** di-commit ke Git karena berisi data sensitif:

- `config.json` - Berisi bot token dan admin ID
- `devices.json` - Berisi kredensial SSH device

## 📦 Dependencies

### Python Packages
- `pyTelegramBotAPI==4.14.0` - Library untuk Telegram Bot API
- `paramiko==3.4.0` - Library untuk koneksi SSH

### System Requirements
- Python 3.6+
- Ubuntu/Debian Linux
- SSH access ke device target
- EarnApp terinstall di device target

## 🚀 Cara Deploy

### 1. Clone Repository
```bash
git clone https://github.com/username/earnapp_bot.git
cd earnapp_bot
```

### 2. Setup Konfigurasi
```bash
# Copy template
cp config.example.json config.json

# Edit dengan data Anda
nano config.json
```

### 3. Install Dependencies
```bash
# Otomatis
sudo bash install.sh

# Atau manual
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Start Bot
```bash
# Via systemd
sudo systemctl start earnapp-bot

# Atau manual
python earnapp_bot.py
```

## 🔧 Konfigurasi

### config.json
```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "admin_telegram_id": "YOUR_TELEGRAM_ID"
}
```

### devices.json
```json
{
  "Local": {
    "type": "local",
    "path": "/usr/bin"
  },
  "Server1": {
    "type": "ssh",
    "host": "192.168.1.100",
    "port": 22,
    "user": "username",
    "password": "password"
  }
}
```

## 📊 Monitoring

### Log Files
- Systemd log: `journalctl -u earnapp-bot -f`
- Manual log: Output console saat run manual

### Status Check
```bash
# Service status
sudo systemctl status earnapp-bot

# Process check
ps aux | grep earnapp_bot

# Port check (jika ada)
netstat -tlnp | grep python
```

## 🔄 Update Process

### 1. Backup Konfigurasi
```bash
cp config.json config.json.backup
cp devices.json devices.json.backup
```

### 2. Update Code
```bash
git pull
```

### 3. Restart Service
```bash
sudo systemctl restart earnapp-bot
```

## 🗑️ Cleanup

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

# Remove files
sudo rm -rf /srv/earnapp_bot
sudo rm /etc/systemd/system/earnapp-bot.service

# Reload systemd
sudo systemctl daemon-reload
```

## 🛡️ Security Notes

1. **Jangan commit file sensitif** - `config.json` dan `devices.json` sudah di-ignore
2. **Gunakan SSH key** - Lebih aman dari password untuk SSH
3. **Restrict bot access** - Hanya admin yang terdaftar bisa akses
4. **Regular update** - Update dependencies secara berkala
5. **Monitor logs** - Pantau log untuk aktivitas mencurigakan

## 📝 Development

### Local Development
```bash
# Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run bot
python earnapp_bot.py
```

### Testing
```bash
# Test SSH connection
python -c "import paramiko; print('SSH OK')"

# Test Telegram API
python -c "import telebot; print('Telegram OK')"
```

## 🤝 Contributing

1. Fork repository
2. Buat feature branch
3. Commit changes
4. Push ke branch
5. Buat Pull Request

## 📞 Support

- GitHub Issues: [Repository Issues](https://github.com/username/earnapp_bot/issues)
- Documentation: Lihat README.md dan INSTALL.md
- Logs: `journalctl -u earnapp-bot -f`
