#!/bin/bash

# Script uninstall EarnApp Bot Web UI
# Jalankan dengan: sudo bash webui/uninstall.sh

echo "🗑️  Memulai uninstall EarnApp Bot Web UI..."

# Stop dan disable service
if systemctl is-active --quiet earnapp-webui; then
    echo "🛑 Menghentikan service..."
    systemctl stop earnapp-webui
fi

if systemctl is-enabled --quiet earnapp-webui; then
    echo "🔌 Menonaktifkan service..."
    systemctl disable earnapp-webui
fi

# Hapus systemd service file
if [ -f "/etc/systemd/system/earnapp-webui.service" ]; then
    echo "🗑️  Menghapus systemd service..."
    rm /etc/systemd/system/earnapp-webui.service
    systemctl daemon-reload
fi

# Konfirmasi hapus file
read -p "⚠️  Apakah Anda yakin ingin menghapus semua file Web UI? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    WEBUI_DIR=$(pwd)
    echo "🗑️  Menghapus file Web UI dari $WEBUI_DIR..."
    
    # Hapus venv
    if [ -d "venv" ]; then
        rm -rf venv
        echo "✅ Virtual environment dihapus"
    fi
    
    # Hapus log files
    if [ -f "webui.log" ]; then
        rm -f webui.log
        echo "✅ Log file dihapus"
    fi
    
    echo "✅ File Web UI dihapus"
    echo "⚠️  Direktori $WEBUI_DIR masih ada, hapus manual jika diperlukan"
else
    echo "❌ Uninstall dibatalkan. File Web UI tetap ada."
fi

echo ""
echo "✅ Uninstall selesai!"

