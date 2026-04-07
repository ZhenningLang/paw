#!/usr/bin/env bash
# Paw tmux paste - clipboard image detection and paste for tmux
# If clipboard contains an image, saves it and sends the file path.
# Otherwise falls back to normal text paste.

set -euo pipefail

PAW_CONFIG_DIR="$HOME/.config/paw"
PAW_CONFIG_FILE="$PAW_CONFIG_DIR/config.json"
PAW_LOG_FILE="$PAW_CONFIG_DIR/paw.log"

SAVE_DIR="$PAW_CONFIG_DIR/images"
FILENAME_FORMAT="%Y%m%d_%H%M%S"
OUTPUT_FORMAT="{path}"

if [ -f "$PAW_CONFIG_FILE" ] && command -v python3 &>/dev/null; then
    eval "$(python3 -c "
import json, os
try:
    with open(os.path.expanduser('$PAW_CONFIG_FILE')) as f:
        cfg = json.load(f).get('paste_image', {})
    d = cfg.get('save_directory', '')
    if d: print(f'SAVE_DIR=\"{d}\"')
    f = cfg.get('filename_format', '')
    if f: print(f'FILENAME_FORMAT=\"{f}\"')
    o = cfg.get('output_format', '')
    if o: print(f'OUTPUT_FORMAT=\"{o}\"')
except: pass
" 2>/dev/null)" || true
fi

SAVE_DIR="${SAVE_DIR/#\~/$HOME}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [tmux-paste] $*" >> "$PAW_LOG_FILE" 2>/dev/null || true
}

paste_text() {
    local text
    text="$(pbpaste 2>/dev/null)" || true
    if [ -n "$text" ]; then
        tmux set-buffer -- "$text"
        tmux paste-buffer -dp
    fi
}

if ! command -v pngpaste &>/dev/null; then
    log "pngpaste not found, falling back to text paste"
    paste_text
    exit 0
fi

# Check if clipboard contains a file reference (e.g. file copied in Finder)
# Must come before pngpaste check, because Finder also puts the file icon
# as an image into the clipboard.
file_path=$(osascript -e 'try
return POSIX path of (the clipboard as «class furl»)
on error
return ""
end try' 2>/dev/null) || true

if [ -n "$file_path" ]; then
    log "Pasted file path: $file_path"
    tmux send-keys -l -- "$file_path"
    exit 0
fi

if pngpaste - > /dev/null 2>&1; then
    mkdir -p "$SAVE_DIR"
    FILENAME="$(date +"$FILENAME_FORMAT").png"
    FILEPATH="$SAVE_DIR/$FILENAME"

    if pngpaste "$FILEPATH" 2>/dev/null && [ -f "$FILEPATH" ]; then
        OUTPUT="${OUTPUT_FORMAT//\{path\}/$FILEPATH}"
        OUTPUT="${OUTPUT//\{filename\}/$FILENAME}"
        OUTPUT="${OUTPUT//\{dir\}/$SAVE_DIR}"

        log "Pasted image: $OUTPUT"
        tmux send-keys -l -- "$OUTPUT"
    else
        rm -f "$FILEPATH"
        log "Failed to save image, falling back to text paste"
        paste_text
    fi
else
    log "No image in clipboard, pasting text"
    paste_text
fi
