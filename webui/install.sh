#!/bin/bash

# Script instalasi EarnApp Bot Web UI
# Jalankan dengan: sudo bash webui/install.sh
# Atau: cd webui && sudo bash install.sh

echo "🌐 Memulai instalasi EarnApp Bot Web UI..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Cek apakah script dijalankan dari dalam webui atau dari root
if [ -f "$SCRIPT_DIR/app.py" ]; then
    # Script dijalankan dari dalam webui
    WEBUI_DIR="$SCRIPT_DIR"
elif [ -f "$SCRIPT_DIR/webui/app.py" ]; then
    # Script dijalankan dari root, webui ada di subdirectory
    WEBUI_DIR="$SCRIPT_DIR/webui"
else
    echo "❌ File app.py tidak ditemukan!"
    echo "Pastikan Anda menjalankan script ini dari root directory atau direktori webui."
    exit 1
fi

cd "$WEBUI_DIR"

# Get root directory (parent of webui)
ROOT_DIR=$(dirname "$WEBUI_DIR")

echo "📁 WebUI Directory: $WEBUI_DIR"
echo "📁 Root Directory: $ROOT_DIR"

# Update sistem
echo "📦 Mengupdate sistem..."
apt update && apt upgrade -y

# Install Python3 dan pip
echo "🐍 Menginstall Python3 dan pip..."
apt install -y python3 python3-pip python3-venv

# Install dependensi sistem untuk paramiko
echo "🔧 Menginstall dependensi sistem..."
apt install -y libffi-dev libssl-dev

# Buat virtual environment di dalam webui
echo "🌐 Membuat virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment sudah ada, menggunakan yang ada..."
else
    python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip
echo "📦 Mengupgrade pip..."
pip install --upgrade pip

# Install Python dependencies
echo "📚 Menginstall dependencies Python..."
if [ -f "../requirements.txt" ]; then
    echo "📋 Menggunakan requirements.txt dari root directory..."
    pip install -r ../requirements.txt
else
    echo "📋 Menggunakan requirements.txt lokal..."
    pip install -r requirements.txt
fi

# Pastikan Flask terinstall
echo "🌐 Memastikan Flask terinstall..."
pip install flask flask-cors

# Buat file konfigurasi jika belum ada
if [ ! -f "$ROOT_DIR/config.json" ]; then
    echo "⚙️ Membuat file konfigurasi..."
    if [ -f "$ROOT_DIR/config.example.json" ]; then
        cp "$ROOT_DIR/config.example.json" "$ROOT_DIR/config.json"
    else
        cat > "$ROOT_DIR/config.json" << EOF
{
  "bot_token": "YOUR_BOT_TOKEN_HERE",
  "admin_telegram_id": "YOUR_TELEGRAM_ID_HERE"
}
EOF
    fi
    echo "⚠️  Silakan edit $ROOT_DIR/config.json dengan konfigurasi Anda"
fi

# Set permission
echo "🔐 Mengatur permission..."
if [ -n "$SUDO_USER" ]; then
    chown -R $SUDO_USER:$SUDO_USER "$WEBUI_DIR"
    chown -R $SUDO_USER:$SUDO_USER "$ROOT_DIR/config.json" 2>/dev/null || true
fi
chmod +x app.py
chmod +x run.sh

# Buat systemd service
echo "🔧 Membuat systemd service..."
SERVICE_USER=${SUDO_USER:-$USER}
WEBUI_AUTH_USERNAME=${WEBUI_AUTH_USERNAME:-admin}
WEBUI_AUTH_PASSWORD=${WEBUI_AUTH_PASSWORD:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')}
WEBUI_HOST=${WEBUI_HOST:-127.0.0.1}
WEBUI_PORT=${WEBUI_PORT:-5000}
WEBUI_ENV_FILE=${WEBUI_ENV_FILE:-/etc/earnapp-webui.env}
install -m 600 -o root -g root /dev/null "$WEBUI_ENV_FILE"
WEBUI_ENV_FILE="$WEBUI_ENV_FILE" \
WEBUI_AUTH_USERNAME="$WEBUI_AUTH_USERNAME" \
WEBUI_AUTH_PASSWORD="$WEBUI_AUTH_PASSWORD" \
WEBUI_HOST="$WEBUI_HOST" \
WEBUI_PORT="$WEBUI_PORT" \
python3 << 'PY'
import os
import shlex

path = os.environ["WEBUI_ENV_FILE"]
keys = ["WEBUI_AUTH_USERNAME", "WEBUI_AUTH_PASSWORD", "WEBUI_HOST", "WEBUI_PORT"]
with open(path, "w") as handle:
    for key in keys:
        handle.write("{0}={1}\n".format(key, shlex.quote(os.environ[key])))
os.chmod(path, 0o600)
PY
cat > /etc/systemd/system/earnapp-webui.service << EOF
[Unit]
Description=EarnApp Bot Web UI Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$WEBUI_DIR
Environment=PATH=$WEBUI_DIR/venv/bin:/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin
EnvironmentFile=$WEBUI_ENV_FILE
ExecStart=$WEBUI_DIR/venv/bin/python $WEBUI_DIR/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd dan enable service
systemctl daemon-reload
systemctl enable earnapp-webui.service

echo "✅ Instalasi Web UI selesai!"
echo ""
echo "📝 Langkah selanjutnya:"
echo "1. Edit file $ROOT_DIR/config.json (jika belum)"
echo "2. Simpan kredensial Web UI di tempat aman"
echo "   Username: $WEBUI_AUTH_USERNAME"
echo "   Password tersimpan di root-only env file: $WEBUI_ENV_FILE"
echo "   Ambil password dengan: sudo sed -n 's/^WEBUI_AUTH_PASSWORD=//p' $WEBUI_ENV_FILE"
echo "3. Start Web UI service"
echo ""
echo "🚀 Cara menjalankan Web UI:"
echo ""
echo "   OPSI 1 - Menggunakan Systemd (RECOMMENDED):"
echo "   sudo systemctl start earnapp-webui"
echo "   sudo systemctl status earnapp-webui"
echo "   sudo systemctl stop earnapp-webui"
echo ""
echo "   OPSI 2 - Menggunakan nohup (tanpa systemd):"
echo "   cd $WEBUI_DIR"
echo "   nohup ./run.sh > webui.log 2>&1 &"
echo ""
echo "   OPSI 3 - Menggunakan screen (tanpa systemd):"
echo "   screen -S earnapp_webui"
echo "   cd $WEBUI_DIR && ./run.sh"
echo "   (Tekan Ctrl+A lalu D untuk detach)"
echo ""
echo "🌐 Web UI akan berjalan di:"
echo "   http://$WEBUI_HOST:$WEBUI_PORT"
echo "   Default bind hanya localhost. Expose lewat reverse proxy/VPN jika perlu akses network."
echo ""
echo "📋 Log Web UI:"
echo "- Systemd: journalctl -u earnapp-webui -f"
echo "- Nohup: tail -f $WEBUI_DIR/webui.log"
