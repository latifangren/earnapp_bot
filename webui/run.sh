#!/bin/bash
# Script untuk menjalankan Web UI
# Bisa dijalankan dari root directory atau dari dalam direktori webui

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Cek apakah script dijalankan dari dalam webui atau dari root
if [ -f "$SCRIPT_DIR/app.py" ]; then
    # Script dijalankan dari dalam webui
    WEBUI_DIR="$SCRIPT_DIR"
    cd "$WEBUI_DIR"
else
    # Script dijalankan dari root directory
    cd "$(dirname "$0")/.."
    WEBUI_DIR="$(pwd)/webui"
fi

# Cek apakah venv ada (prioritas: venv di webui, lalu venv di parent)
if [ -d "$WEBUI_DIR/venv" ]; then
    VENV_DIR="$WEBUI_DIR/venv"
    echo "🌐 Menggunakan virtual environment di webui/venv..."
elif [ -d "$(dirname "$WEBUI_DIR")/venv" ]; then
    VENV_DIR="$(dirname "$WEBUI_DIR")/venv"
    echo "🌐 Menggunakan virtual environment di parent directory..."
else
    VENV_DIR=""
fi

# Cek apakah venv ada, jika ada gunakan venv
if [ -n "$VENV_DIR" ] && [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    
    # Cek apakah Flask sudah terinstall
    if ! python -c "import flask" 2>/dev/null; then
        echo "📦 Flask belum terinstall, menginstall dependencies..."
        # Coba install dari requirements.txt di root atau webui
        if [ -f "$(dirname "$WEBUI_DIR")/requirements.txt" ]; then
            pip install -r "$(dirname "$WEBUI_DIR")/requirements.txt"
        elif [ -f "$WEBUI_DIR/requirements.txt" ]; then
            pip install -r "$WEBUI_DIR/requirements.txt"
        fi
        # Install Flask secara eksplisit jika masih belum ada
        if ! python -c "import flask" 2>/dev/null; then
            echo "📦 Menginstall Flask secara eksplisit..."
            pip install flask==3.0.0 flask-cors==4.0.0
        fi
    fi
    
    # Jalankan app.py
    if [ -f "$WEBUI_DIR/app.py" ]; then
        cd "$WEBUI_DIR"
        python app.py
    else
        echo "❌ File app.py tidak ditemukan di $WEBUI_DIR"
        exit 1
    fi
else
    echo "⚠️  Virtual environment tidak ditemukan!"
    echo "📝 Membuat virtual environment di webui/venv..."
    cd "$WEBUI_DIR"
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Menginstall dependencies..."
    # Coba install dari requirements.txt di root atau webui
    if [ -f "$(dirname "$WEBUI_DIR")/requirements.txt" ]; then
        pip install -r "$(dirname "$WEBUI_DIR")/requirements.txt"
    elif [ -f "$WEBUI_DIR/requirements.txt" ]; then
        pip install -r "$WEBUI_DIR/requirements.txt"
    fi
    # Pastikan Flask terinstall
    pip install flask flask-cors
    echo "🚀 Menjalankan Web UI..."
    python app.py
fi
