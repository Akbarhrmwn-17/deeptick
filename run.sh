#!/bin/bash
# run.sh — Script untuk menjalankan Saham Monitor
# Cara pakai: bash run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🇮🇩 Saham Monitor — Starting..."
echo "==============================="

# Cek apakah streamlit tersedia
if command -v streamlit &> /dev/null; then
    STREAMLIT_CMD="streamlit"
elif [ -f "$HOME/.local/bin/streamlit" ]; then
    STREAMLIT_CMD="$HOME/.local/bin/streamlit"
else
    echo "❌ Streamlit tidak ditemukan. Install dulu dengan:"
    echo "   python3 -m pip install streamlit --break-system-packages"
    exit 1
fi

echo "✅ Streamlit ditemukan: $(which streamlit 2>/dev/null || echo $HOME/.local/bin/streamlit)"
echo "📂 Direktori: $SCRIPT_DIR"
echo ""
echo "🚀 Menjalankan app di http://localhost:8501"
echo "   Tekan Ctrl+C untuk berhenti"
echo ""

$STREAMLIT_CMD run app.py \
    --server.port 8501 \
    --server.address localhost \
    --browser.gatherUsageStats false \
    --theme.base dark \
    --theme.primaryColor "#00C853" \
    --theme.backgroundColor "#0d1117" \
    --theme.secondaryBackgroundColor "#161b22" \
    --theme.textColor "#e6edf3"
