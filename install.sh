#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/paw"

echo "=== Paw - Terminal Text Enhancement ==="
echo

mkdir -p "$CONFIG_DIR"

# Copy all source files
for f in paw_cli.py paw_segmenter.py paw.zsh paw.py; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$CONFIG_DIR/$f"
    fi
done

# Ensure venv exists (needed by CLI)
if [ ! -d "$CONFIG_DIR/venv" ]; then
    echo "[*] Creating Python venv..."
    python3 -m venv "$CONFIG_DIR/venv"
    "$CONFIG_DIR/venv/bin/pip" install jieba -q 2>&1 | grep -v "notice"
    echo "[OK] venv + jieba ready"
fi

# Install paw command
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/paw" << 'EOF'
#!/bin/bash
exec python3 "$HOME/.config/paw/paw_cli.py" "$@"
EOF
chmod +x "$BIN_DIR/paw"
echo "[OK] Installed 'paw' command to $BIN_DIR/paw"

# Check PATH
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    echo "[Info] Add to PATH if not already: export PATH=\"$BIN_DIR:\$PATH\""
fi

echo
echo "Run 'paw' to manage features interactively."
echo
