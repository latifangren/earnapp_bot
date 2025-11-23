#!/bin/bash

# Script instalasi EarnApp Bot
# Jalankan dengan: sudo bash install.sh

echo "🤖 Memulai instalasi EarnApp Bot..."

# Cek apakah file bot ada
if [ ! -f "earnapp_bot.py" ]; then
    echo "❌ File earnapp_bot.py tidak ditemukan!"
    echo "Pastikan Anda menjalankan script ini dari direktori yang berisi file bot."
    exit 1
fi

# Update sistem
echo "📦 Mengupdate sistem..."
apt update && apt upgrade -y

# Install Python3 dan pip
echo "🐍 Menginstall Python3 dan pip..."
apt install -y python3 python3-pip python3-venv

# Install dependensi sistem untuk paramiko
echo "🔧 Menginstall dependensi sistem..."
apt install -y libffi-dev libssl-dev

# Buat direktori untuk bot
echo "📁 Membuat direktori bot..."
mkdir -p /srv/earnapp_bot

# Salin file dari direktori saat ini ke /srv/earnapp_bot
echo "📋 Menyalin file bot..."
cp earnapp_bot.py /srv/earnapp_bot/
cp requirements.txt /srv/earnapp_bot/
cp config.example.json /srv/earnapp_bot/
cp *.md /srv/earnapp_bot/ 2>/dev/null || true
cp *.sh /srv/earnapp_bot/ 2>/dev/null || true
cp LICENSE /srv/earnapp_bot/ 2>/dev/null || true

# Pindah ke direktori bot
cd /srv/earnapp_bot

# Buat virtual environment
echo "🌐 Membuat virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📚 Menginstall dependencies Python..."
pip install -r requirements.txt

# Buat file konfigurasi jika belum ada
if [ ! -f "config.json" ]; then
    echo "⚙️ Membuat file konfigurasi..."
    cp config.example.json config.json
fi

# Buat file devices.json jika belum ada
if [ ! -f "devices.json" ]; then
    echo "📱 Membuat file devices..."
    cat > devices.json << EOF
{
  "Local": {
    "type": "local",
    "path": "/usr/bin"
  }
}
EOF
fi

# Set permission
echo "🔐 Mengatur permission..."
chown -R $SUDO_USER:$SUDO_USER /srv/earnapp_bot
chmod +x earnapp_bot.py

# Buat systemd service
echo "🔧 Membuat systemd service..."
cat > /etc/systemd/system/earnapp-bot.service << EOF
[Unit]
Description=EarnApp Bot Service
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=/srv/earnapp_bot
Environment=PATH=/srv/earnapp_bot/venv/bin:/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin
ExecStart=/srv/earnapp_bot/venv/bin/python earnapp_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd dan enable service
systemctl daemon-reload
systemctl enable earnapp-bot.service

# Buat script alternatif untuk menjalankan tanpa systemd (opsional)
echo "📝 Membuat script alternatif..."
cat > /srv/earnapp_bot/run_bot.sh << 'SCRIPT_EOF'
#!/bin/bash
# Script untuk menjalankan bot tanpa systemd
# Gunakan nohup atau screen/tmux untuk menjalankan di background

cd /srv/earnapp_bot
source venv/bin/activate
python earnapp_bot.py
SCRIPT_EOF
chmod +x /srv/earnapp_bot/run_bot.sh

echo "✅ Instalasi selesai!"
echo ""
echo "📝 Langkah selanjutnya:"
echo "1. Edit file /srv/earnapp_bot/config.json"
echo "2. Masukkan bot token dan telegram ID Anda"
echo ""
echo "🚀 Cara menjalankan bot:"
echo ""
echo "   OPSI 1 - Menggunakan Systemd (RECOMMENDED):"
echo "   sudo systemctl start earnapp-bot"
echo "   sudo systemctl status earnapp-bot"
echo "   sudo systemctl stop earnapp-bot"
echo ""
echo "   OPSI 2 - Menggunakan nohup (tanpa systemd):"
echo "   cd /srv/earnapp_bot"
echo "   nohup ./run_bot.sh > bot.log 2>&1 &"
echo ""
echo "   OPSI 3 - Menggunakan screen (tanpa systemd):"
echo "   screen -S earnapp_bot"
echo "   cd /srv/earnapp_bot && ./run_bot.sh"
echo "   (Tekan Ctrl+A lalu D untuk detach)"
echo ""
echo "⚠️  PENTING:"
echo "   - Fitur auto restart dan time-based schedule menggunakan background threads"
echo "   - Thread ini hanya berjalan jika bot Python berjalan"
echo "   - Systemd service memastikan bot selalu berjalan (auto restart jika crash)"
echo "   - Tanpa systemd/daemon, bot bisa mati dan fitur auto tidak akan jalan"
echo "   - RECOMMENDED: Gunakan systemd untuk production"
echo ""
echo "🔧 File konfigurasi:"
echo "- Bot Token: /srv/earnapp_bot/config.json"
echo "- Devices: /srv/earnapp_bot/devices.json"
echo ""
echo "📋 Log bot:"
echo "- Systemd: journalctl -u earnapp-bot -f"
echo "- Nohup: tail -f /srv/earnapp_bot/bot.log"
