#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/paw"
ITERM2_SCRIPTS_DIR="$HOME/Library/Application Support/iTerm2/Scripts"

echo "=== Paw - Terminal Text Enhancement ==="
echo

# Feature selection
echo "Select features to enable:"
echo ""

HAS_ITERM2=false
[ -d "/Applications/iTerm.app" ] && HAS_ITERM2=true

if $HAS_ITERM2; then
    read -p "  [1] Clipboard image pasting - Cmd+V (iTerm2 plugin)? [Y/n] " -n 1 -r PASTE_IMG
    echo
    PASTE_IMG=${PASTE_IMG:-Y}
else
    echo "  [1] Clipboard image pasting - skipped (iTerm2 not found)"
    PASTE_IMG=n
fi

read -p "  [2] Chinese word jump - Option+Arrow (zsh widget)? [Y/n] " -n 1 -r WORD_JUMP
echo
WORD_JUMP=${WORD_JUMP:-Y}

read -p "  [3] Chinese word delete - Option+Delete (zsh widget)? [Y/n] " -n 1 -r WORD_DEL
echo
WORD_DEL=${WORD_DEL:-Y}

if $HAS_ITERM2; then
    read -p "  [4] Cmd+Z undo in terminal (iTerm2 key mapping)? [Y/n] " -n 1 -r UNDO_MAP
    echo
    UNDO_MAP=${UNDO_MAP:-Y}
else
    UNDO_MAP=n
fi

echo

mkdir -p "$CONFIG_DIR"

# ── Word segmentation features (zsh widget + daemon) ──

if [[ $WORD_JUMP =~ ^[Yy]$ ]] || [[ $WORD_DEL =~ ^[Yy]$ ]]; then
    echo "[*] Setting up word segmentation..."

    # Create venv with jieba
    if [ ! -d "$CONFIG_DIR/venv" ]; then
        echo "    Creating Python venv..."
        python3 -m venv "$CONFIG_DIR/venv"
    fi

    echo "    Installing jieba..."
    "$CONFIG_DIR/venv/bin/pip" install jieba -q 2>&1 | grep -v "notice"
    echo "[OK] jieba installed"

    # Copy segmenter daemon
    cp "$SCRIPT_DIR/paw_segmenter.py" "$CONFIG_DIR/paw_segmenter.py"
    echo "[OK] Segmenter daemon installed"

    # Copy zsh widget
    cp "$SCRIPT_DIR/paw.zsh" "$CONFIG_DIR/paw.zsh"
    echo "[OK] Zsh widget installed"

    # Add to .zshrc if not already
    ZSHRC="$HOME/.zshrc"
    SOURCE_LINE="source \"$CONFIG_DIR/paw.zsh\""
    if ! grep -qF "paw.zsh" "$ZSHRC" 2>/dev/null; then
        echo "" >> "$ZSHRC"
        echo "# Paw - Terminal Text Enhancement" >> "$ZSHRC"
        echo "$SOURCE_LINE" >> "$ZSHRC"
        echo "[OK] Added to ~/.zshrc"
    else
        echo "[Skip] Already in ~/.zshrc"
    fi

    # Start daemon
    pkill -f paw_segmenter 2>/dev/null || true
    rm -f "$CONFIG_DIR/paw.sock" "$CONFIG_DIR/paw.pid"
    "$CONFIG_DIR/venv/bin/python3" "$CONFIG_DIR/paw_segmenter.py" &>/dev/null &
    disown
    sleep 1
    if [ -f "$CONFIG_DIR/paw.pid" ]; then
        echo "[OK] Segmenter daemon started (pid $(cat "$CONFIG_DIR/paw.pid"))"
    else
        echo "[Warning] Daemon may not have started, check logs"
    fi
fi

# ── Image paste feature (iTerm2 plugin) ──

if [[ $PASTE_IMG =~ ^[Yy]$ ]] && $HAS_ITERM2; then
    # Check Python API
    PYTHON_API_ENABLED=$(defaults read com.googlecode.iterm2 EnableAPIServer 2>/dev/null || echo "0")
    if [ "$PYTHON_API_ENABLED" != "1" ]; then
        echo ""
        echo "[Warning] iTerm2 Python API is NOT enabled!"
        echo "  Settings (Cmd+,) → General → Magic → Enable Python API"
        echo ""
    fi

    # Optional: pngpaste
    if ! command -v pngpaste &>/dev/null; then
        echo "[Info] pngpaste not found (optional): brew install pngpaste"
    fi

    # Install iTerm2 plugin
    mkdir -p "$ITERM2_SCRIPTS_DIR"
    cp "$SCRIPT_DIR/paw.py" "$ITERM2_SCRIPTS_DIR/"

    # Remove old paste_image.py
    rm -f "$ITERM2_SCRIPTS_DIR/paste_image.py"
    rm -f "$ITERM2_SCRIPTS_DIR/AutoLaunch/paste_image.py"

    # AutoLaunch
    AUTOLAUNCH_DIR="$ITERM2_SCRIPTS_DIR/AutoLaunch"
    mkdir -p "$AUTOLAUNCH_DIR"
    ln -sf "$ITERM2_SCRIPTS_DIR/paw.py" "$AUTOLAUNCH_DIR/paw.py"
    echo "[OK] iTerm2 image paste plugin installed"

    mkdir -p "$CONFIG_DIR/images"
fi

# ── Cmd+Z undo key mapping ──

if [[ $UNDO_MAP =~ ^[Yy]$ ]] && $HAS_ITERM2; then
    python3 << 'PYEOF'
import plistlib, os, sys

plist_path = os.path.expanduser("~/Library/Preferences/com.googlecode.iterm2.plist")
try:
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
except Exception as e:
    print(f"[Warning] Cannot read iTerm2 plist: {e}")
    sys.exit(0)

KEY = "0x7a-0x100000-0x6"  # Cmd+Z
MAPPING = {"Action": 11, "Text": "0x1f", "Version": 2, "Apply Mode": 0, "Escaping": 2}
changed = False

for bookmark in data.get("New Bookmarks", []):
    km = bookmark.setdefault("Keyboard Map", {})
    if KEY not in km:
        km[KEY] = MAPPING
        changed = True
        print(f'[OK] Added Cmd+Z → undo to profile "{bookmark.get("Name", "?")}"')
    else:
        print(f'[Skip] Cmd+Z already mapped in profile "{bookmark.get("Name", "?")}"')

if changed:
    with open(plist_path, "wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)
PYEOF
fi

# ── Config file ──

if [ ! -f "$CONFIG_DIR/config.json" ]; then
    FEAT_PASTE=$([[ $PASTE_IMG =~ ^[Yy]$ ]] && echo "true" || echo "false")
    FEAT_JUMP=$([[ $WORD_JUMP =~ ^[Yy]$ ]] && echo "true" || echo "false")
    FEAT_DEL=$([[ $WORD_DEL =~ ^[Yy]$ ]] && echo "true" || echo "false")

    cat > "$CONFIG_DIR/config.json" << EOF
{
    "features": {
        "paste_image": $FEAT_PASTE,
        "word_jump": $FEAT_JUMP,
        "word_delete": $FEAT_DEL
    },
    "paste_image": {
        "save_directory": "~/.config/paw/images",
        "filename_format": "%Y%m%d_%H%M%S",
        "output_format": "{path}"
    }
}
EOF
    echo "[OK] Config: $CONFIG_DIR/config.json"
fi

echo
echo "=== Installation Complete ==="
echo
if [[ $WORD_JUMP =~ ^[Yy]$ ]] || [[ $WORD_DEL =~ ^[Yy]$ ]]; then
    echo "Word segmentation: run 'source ~/.zshrc' or open a new terminal"
fi
if [[ $PASTE_IMG =~ ^[Yy]$ ]] && $HAS_ITERM2; then
    echo "Image paste: restart iTerm2 to activate"
fi
echo
