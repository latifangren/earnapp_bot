#!/bin/bash

# Script uninstall EarnApp Bot
# Jalankan dengan: sudo bash uninstall.sh

echo "🗑️ Memulai proses uninstall EarnApp Bot..."

# Konfirmasi uninstall
read -p "⚠️ Apakah Anda yakin ingin menghapus EarnApp Bot? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Uninstall dibatalkan."
    exit 1
fi

echo "🛑 Menghentikan service..."

# Stop dan disable service
if systemctl is-active --quiet earnapp-bot; then
    echo "⏹️ Menghentikan earnapp-bot service..."
    systemctl stop earnapp-bot
else
    echo "ℹ️ Service earnapp-bot sudah berhenti."
fi

if systemctl is-enabled --quiet earnapp-bot; then
    echo "🔌 Menonaktifkan earnapp-bot service..."
    systemctl disable earnapp-bot
else
    echo "ℹ️ Service earnapp-bot sudah dinonaktifkan."
fi

echo "🗑️ Menghapus service file..."

# Hapus service file
if [ -f "/etc/systemd/system/earnapp-bot.service" ]; then
    rm /etc/systemd/system/earnapp-bot.service
    echo "✅ Service file dihapus."
else
    echo "ℹ️ Service file tidak ditemukan."
fi

echo "🔄 Reload systemd daemon..."
systemctl daemon-reload

echo "📁 Menghapus direktori bot..."

# Backup konfigurasi jika diminta
read -p "💾 Apakah Anda ingin backup konfigurasi sebelum dihapus? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    BACKUP_DIR="/tmp/earnapp_bot_backup_$(date +%Y%m%d_%H%M%S)"
    echo "📦 Membuat backup ke: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    if [ -d "/srv/earnapp_bot" ]; then
        cp -r /srv/earnapp_bot/* "$BACKUP_DIR/" 2>/dev/null || true
        echo "✅ Backup selesai: $BACKUP_DIR"
    fi
fi

# Hapus direktori bot
if [ -d "/srv/earnapp_bot" ]; then
    echo "🗑️ Menghapus direktori /srv/earnapp_bot..."
    rm -rf /srv/earnapp_bot
    echo "✅ Direktori bot dihapus."
else
    echo "ℹ️ Direktori /srv/earnapp_bot tidak ditemukan."
fi

echo "🧹 Membersihkan file temporary..."

# Hapus file temporary jika ada
rm -f /tmp/earnapp_bot_*.log 2>/dev/null || true
rm -f /tmp/earnapp_bot_*.pid 2>/dev/null || true

echo "🔍 Mencari file konfigurasi tersisa..."

# Cari file konfigurasi di lokasi lain
CONFIG_FILES=(
    "$HOME/.earnapp_bot"
    "$HOME/.config/earnapp_bot"
    "/etc/earnapp_bot"
    "/var/log/earnapp_bot"
)

for config_dir in "${CONFIG_FILES[@]}"; do
    if [ -d "$config_dir" ]; then
        echo "⚠️ Ditemukan direktori konfigurasi: $config_dir"
        read -p "🗑️ Hapus direktori ini? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$config_dir"
            echo "✅ Direktori $config_dir dihapus."
        fi
    fi
done

echo "🔍 Mencari process yang masih berjalan..."

# Cek apakah masih ada process earnapp_bot yang berjalan
PIDS=$(pgrep -f "earnapp_bot.py" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo "⚠️ Ditemukan process earnapp_bot yang masih berjalan:"
    ps aux | grep earnapp_bot.py | grep -v grep
    read -p "🛑 Kill process ini? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill -9 $PIDS 2>/dev/null || true
        echo "✅ Process dihentikan."
    fi
else
    echo "✅ Tidak ada process earnapp_bot yang berjalan."
fi

echo "🧹 Membersihkan log systemd..."

# Hapus log systemd untuk service ini
if command -v journalctl >/dev/null 2>&1; then
    echo "🗑️ Menghapus log systemd untuk earnapp-bot..."
    journalctl --vacuum-time=1s --unit=earnapp-bot >/dev/null 2>&1 || true
    echo "✅ Log systemd dibersihkan."
fi

echo "🔍 Mencari file Python cache..."

# Hapus Python cache
find /srv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find /home -name "__pycache__" -path "*/earnapp_bot/*" -type d -exec rm -rf {} + 2>/dev/null || true
find /tmp -name "*earnapp_bot*" -type f -delete 2>/dev/null || true

echo "✅ Python cache dibersihkan."

echo "🔍 Mencari file konfigurasi di home directory..."

# Cek file konfigurasi di home directory
if [ -f "$HOME/.earnapp_bot_config.json" ]; then
    read -p "🗑️ Hapus file konfigurasi di home: $HOME/.earnapp_bot_config.json? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$HOME/.earnapp_bot_config.json"
        echo "✅ File konfigurasi di home dihapus."
    fi
fi

echo "🔍 Mencari cron job terkait earnapp_bot..."

# Cek cron job
if crontab -l 2>/dev/null | grep -q "earnapp_bot"; then
    echo "⚠️ Ditemukan cron job terkait earnapp_bot:"
    crontab -l | grep earnapp_bot
    read -p "🗑️ Hapus cron job ini? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        crontab -l | grep -v "earnapp_bot" | crontab -
        echo "✅ Cron job dihapus."
    fi
fi

echo "🔍 Mencari alias atau function terkait earnapp_bot..."

# Cek alias di shell profile
SHELL_PROFILES=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.bash_profile")
for profile in "${SHELL_PROFILES[@]}"; do
    if [ -f "$profile" ] && grep -q "earnapp_bot" "$profile"; then
        echo "⚠️ Ditemukan referensi earnapp_bot di: $profile"
        read -p "🗑️ Hapus referensi ini? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sed -i '/earnapp_bot/d' "$profile"
            echo "✅ Referensi dihapus dari $profile"
        fi
    fi
done

echo "🧹 Membersihkan package Python (opsional)..."

read -p "🗑️ Hapus package Python earnapp_bot dari sistem? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Hapus dari pip jika terinstall
    pip uninstall -y earnapp_bot 2>/dev/null || true
    pip3 uninstall -y earnapp_bot 2>/dev/null || true
    echo "✅ Package Python dibersihkan."
fi

echo "🔍 Verifikasi uninstall..."

# Verifikasi bahwa semua file sudah dihapus
if [ -d "/srv/earnapp_bot" ]; then
    echo "❌ Peringatan: Direktori /srv/earnapp_bot masih ada!"
else
    echo "✅ Direktori /srv/earnapp_bot sudah dihapus."
fi

if [ -f "/etc/systemd/system/earnapp-bot.service" ]; then
    echo "❌ Peringatan: Service file masih ada!"
else
    echo "✅ Service file sudah dihapus."
fi

if systemctl is-active --quiet earnapp-bot 2>/dev/null; then
    echo "❌ Peringatan: Service masih aktif!"
else
    echo "✅ Service sudah dihentikan."
fi

echo ""
echo "🎉 Uninstall EarnApp Bot selesai!"
echo ""
echo "📋 Ringkasan:"
echo "✅ Service dihentikan dan dinonaktifkan"
echo "✅ File service dihapus"
echo "✅ Direktori bot dihapus"
echo "✅ Log dibersihkan"
echo "✅ Process dihentikan"
echo "✅ File temporary dibersihkan"
echo ""
echo "💡 Tips:"
echo "- Jika Anda membuat backup, cek di /tmp/earnapp_bot_backup_*"
echo "- Restart sistem untuk memastikan semua proses bersih"
echo "- Jika ada masalah, cek log: journalctl -u earnapp-bot"
echo ""
echo "👋 Terima kasih telah menggunakan EarnApp Bot!"
