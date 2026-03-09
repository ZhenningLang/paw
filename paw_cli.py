#!/usr/bin/env python3
"""
Paw CLI - Terminal Text Enhancement Manager
Usage: paw [status|diagnose|daemon start|stop|restart]
"""

import os
import sys
import shutil
import signal
import socket
import platform
import subprocess
import plistlib
from pathlib import Path

VERSION = "0.1.0"
HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "paw"
VENV_DIR = CONFIG_DIR / "venv"
VENV_PYTHON = VENV_DIR / "bin" / "python3"
SEGMENTER_PATH = CONFIG_DIR / "paw_segmenter.py"
ZSH_WIDGET_PATH = CONFIG_DIR / "paw.zsh"
PID_FILE = CONFIG_DIR / "paw.pid"
SOCK_FILE = CONFIG_DIR / "paw.sock"
ZSHRC = HOME / ".zshrc"
ITERM2_PLIST = HOME / "Library" / "Preferences" / "com.googlecode.iterm2.plist"
ITERM2_SCRIPTS = HOME / "Library" / "Application Support" / "iTerm2" / "Scripts"
ITERM2_AUTOLAUNCH = ITERM2_SCRIPTS / "AutoLaunch"
# Source repo (where this script lives)
REPO_DIR = Path(__file__).resolve().parent

# ── Terminal colors ─────────────────────────────────────────────────

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

def ok(s): return f"{GREEN}✓{RESET} {s}"
def fail(s): return f"{RED}✗{RESET} {s}"
def warn(s): return f"{YELLOW}!{RESET} {s}"
def dim(s): return f"{DIM}{s}{RESET}"
def bold(s): return f"{BOLD}{s}{RESET}"

# ── Environment detection ──────────────────────────────────────────

def detect_env():
    env = {}
    env["os"] = f"{platform.system()} {platform.mac_ver()[0] or platform.release()}"
    env["shell"] = os.environ.get("SHELL", "unknown")
    shell_name = Path(env["shell"]).name
    env["shell_name"] = shell_name
    if shell_name == "zsh":
        r = subprocess.run(["zsh", "--version"], capture_output=True, text=True, timeout=5)
        env["shell_version"] = r.stdout.strip().split("\n")[0] if r.returncode == 0 else "?"
    else:
        env["shell_version"] = shell_name
    env["python"] = f"{platform.python_version()} ({sys.executable})"
    env["terminal"] = os.environ.get("TERM_PROGRAM", "unknown")
    env["terminal_version"] = os.environ.get("TERM_PROGRAM_VERSION", "")
    env["has_iterm2"] = Path("/Applications/iTerm.app").is_dir()
    env["has_nc"] = shutil.which("nc") is not None
    env["has_pngpaste"] = shutil.which("pngpaste") is not None
    return env

# ── Feature status checks ──────────────────────────────────────────

class Feature:
    def __init__(self, key, name, check_fn, enable_fn, disable_fn, requires_terminal=None):
        self.key = key
        self.name = name
        self._check = check_fn
        self._enable = enable_fn
        self._disable = disable_fn
        self.requires_terminal = requires_terminal

    def check(self):
        """Returns (enabled: bool, detail: str)"""
        return self._check()

    def enable(self):
        return self._enable()

    def disable(self):
        return self._disable()

    def available(self, env):
        if self.requires_terminal and not env.get(f"has_{self.requires_terminal}"):
            return False
        if self.key in ("word_jump", "word_delete") and env.get("shell_name") != "zsh":
            return False
        return True


# ── Check functions ─────────────────────────────────────────────────

def _daemon_pid():
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return pid
        except (ProcessLookupError, ValueError, PermissionError):
            pass
    return None

def _daemon_responsive():
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(str(SOCK_FILE))
        s.sendall(b"hello\t0\tnext_word\n")
        r = s.recv(1024).decode().strip()
        s.close()
        return r.isdigit()
    except Exception:
        return False

def _zshrc_has_paw():
    if ZSHRC.exists():
        return "paw.zsh" in ZSHRC.read_text()
    return False

def _jieba_importable():
    if not VENV_PYTHON.exists():
        return False
    r = subprocess.run(
        [str(VENV_PYTHON), "-c", "import jieba"],
        capture_output=True, timeout=10,
    )
    return r.returncode == 0

def check_word_jump():
    if not _zshrc_has_paw():
        return False, "not in .zshrc"
    if not ZSH_WIDGET_PATH.exists():
        return False, "paw.zsh missing"
    pid = _daemon_pid()
    if pid:
        return True, f"daemon running (pid {pid})"
    return True, dim("daemon not running")

def check_word_delete():
    # Shares infrastructure with word_jump
    if not _zshrc_has_paw():
        return False, "not in .zshrc"
    if not ZSH_WIDGET_PATH.exists():
        return False, "paw.zsh missing"
    return True, ""

def check_image_paste():
    plugin_exists = (ITERM2_SCRIPTS / "paw.py").exists()
    autolaunch = (ITERM2_AUTOLAUNCH / "paw.py").exists() or (ITERM2_AUTOLAUNCH / "paw.py").is_symlink()
    api_enabled = _iterm2_api_enabled()
    if not api_enabled:
        if plugin_exists:
            return True, warn("Python API not enabled")
        return False, "Python API not enabled"
    if not plugin_exists:
        return False, "plugin not installed"
    if not autolaunch:
        return True, warn("AutoLaunch not configured")
    # Check if process running
    r = subprocess.run(["pgrep", "-f", "paw.py.*iterm2"], capture_output=True, text=True)
    if r.returncode == 0:
        return True, "running"
    return True, dim("not running (restart iTerm2)")

def check_cmd_z():
    try:
        with open(ITERM2_PLIST, "rb") as f:
            data = plistlib.load(f)
        bookmarks = data.get("New Bookmarks", [])
        total = len(bookmarks)
        mapped = sum(1 for b in bookmarks if "0x7a-0x100000-0x6" in b.get("Keyboard Map", {}))
        if mapped == total:
            return True, f"{mapped}/{total} profiles"
        if mapped > 0:
            return True, warn(f"{mapped}/{total} profiles")
        return False, f"0/{total} profiles"
    except Exception:
        return False, "cannot read plist"

def _iterm2_api_enabled():
    r = subprocess.run(
        ["defaults", "read", "com.googlecode.iterm2", "EnableAPIServer"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() == "1"

# ── Enable functions ────────────────────────────────────────────────

def _ensure_venv():
    if not VENV_DIR.exists():
        print("  Creating Python venv...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    if not _jieba_importable():
        print("  Installing jieba...")
        subprocess.run(
            [str(VENV_DIR / "bin" / "pip"), "install", "jieba", "-q"],
            capture_output=True, check=True,
        )
    print(f"  {ok('venv + jieba ready')}")

def _copy_segmenter():
    src = REPO_DIR / "paw_segmenter.py"
    if src.exists():
        shutil.copy2(src, SEGMENTER_PATH)
    elif not SEGMENTER_PATH.exists():
        print(f"  {fail('paw_segmenter.py not found in ' + str(REPO_DIR))}")
        return False
    return True

def _copy_zsh_widget():
    src = REPO_DIR / "paw.zsh"
    if src.exists():
        shutil.copy2(src, ZSH_WIDGET_PATH)
    elif not ZSH_WIDGET_PATH.exists():
        print(f"  {fail('paw.zsh not found in ' + str(REPO_DIR))}")
        return False
    return True

def _add_to_zshrc():
    if _zshrc_has_paw():
        return
    with open(ZSHRC, "a") as f:
        f.write(f'\n# Paw - Terminal Text Enhancement\nsource "{ZSH_WIDGET_PATH}"\n')
    print(f"  {ok('added to ~/.zshrc')}")

def _remove_from_zshrc():
    if not ZSHRC.exists():
        return
    lines = ZSHRC.read_text().splitlines(keepends=True)
    new = []
    skip_next = False
    for line in lines:
        if "Paw - Terminal Text Enhancement" in line:
            skip_next = True
            continue
        if skip_next and "paw.zsh" in line:
            skip_next = False
            continue
        skip_next = False
        new.append(line)
    ZSHRC.write_text("".join(new))
    print(f"  {ok('removed from ~/.zshrc')}")

def daemon_start():
    pid = _daemon_pid()
    if pid:
        print(f"  {ok(f'daemon already running (pid {pid})')}")
        return
    _cleanup_stale_daemon()
    subprocess.Popen(
        [str(VENV_PYTHON), str(SEGMENTER_PATH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    import time; time.sleep(1)
    pid = _daemon_pid()
    if pid:
        print(f"  {ok(f'daemon started (pid {pid})')}")
    else:
        print(f"  {fail('daemon failed to start')}")

def daemon_stop():
    pid = _daemon_pid()
    if pid:
        os.kill(pid, signal.SIGTERM)
        print(f"  {ok(f'daemon stopped (was pid {pid})')}")
    else:
        print(f"  {dim('daemon not running')}")
    _cleanup_stale_daemon()

def daemon_restart():
    daemon_stop()
    import time; time.sleep(0.5)
    daemon_start()

def _cleanup_stale_daemon():
    for f in (PID_FILE, SOCK_FILE):
        try: f.unlink()
        except FileNotFoundError: pass

def enable_word_seg():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_venv()
    _copy_segmenter()
    _copy_zsh_widget()
    _add_to_zshrc()
    daemon_start()
    print(f"  {ok('word segmentation enabled')}")
    print(f"  {dim('run: source ~/.zshrc  (or open new terminal)')}")

def disable_word_seg():
    daemon_stop()
    _remove_from_zshrc()
    print(f"  {ok('word segmentation disabled')}")

def enable_image_paste():
    if not _iterm2_api_enabled():
        print(f"\n  {warn('iTerm2 Python API must be enabled first:')}")
        print(f"  Settings (Cmd+,) → General → Magic → Enable Python API\n")
        print(f"  Waiting for Python API to be enabled... (Ctrl+C to skip)")
        import time
        try:
            while not _iterm2_api_enabled():
                time.sleep(2)
            print(f"  {ok('Python API detected!')}")
        except KeyboardInterrupt:
            print(f"\n  {dim('skipped')}")

    ITERM2_SCRIPTS.mkdir(parents=True, exist_ok=True)
    ITERM2_AUTOLAUNCH.mkdir(parents=True, exist_ok=True)

    src = REPO_DIR / "paw.py"
    dest = ITERM2_SCRIPTS / "paw.py"
    if src.exists():
        shutil.copy2(src, dest)
    elif not dest.exists():
        print(f"  {fail('paw.py not found')}")
        return

    link = ITERM2_AUTOLAUNCH / "paw.py"
    link.unlink(missing_ok=True)
    link.symlink_to(dest)

    (CONFIG_DIR / "images").mkdir(parents=True, exist_ok=True)
    print(f"  {ok('image paste plugin installed')}")
    print(f"  {dim('restart iTerm2 to activate')}")

def disable_image_paste():
    (ITERM2_AUTOLAUNCH / "paw.py").unlink(missing_ok=True)
    (ITERM2_SCRIPTS / "paw.py").unlink(missing_ok=True)
    print(f"  {ok('image paste plugin removed')}")

def enable_cmd_z():
    try:
        with open(ITERM2_PLIST, "rb") as f:
            data = plistlib.load(f)
    except Exception as e:
        print(f"  {fail(f'cannot read plist: {e}')}")
        return

    KEY = "0x7a-0x100000-0x6"
    MAPPING = {"Action": 11, "Text": "0x1f", "Version": 2, "Apply Mode": 0, "Escaping": 2}
    changed = False

    for b in data.get("New Bookmarks", []):
        km = b.setdefault("Keyboard Map", {})
        if KEY not in km:
            km[KEY] = MAPPING
            changed = True
            name = b.get("Name", "?")
            print(f"  {ok('added to profile \"' + name + '\"')}")
        else:
            name = b.get("Name", "?")
            print(f"  {dim('already mapped in \"' + name + '\"')}")

    if changed:
        with open(ITERM2_PLIST, "wb") as f:
            plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)

def disable_cmd_z():
    try:
        with open(ITERM2_PLIST, "rb") as f:
            data = plistlib.load(f)
    except Exception as e:
        print(f"  {fail('cannot read plist: ' + str(e))}")
        return

    KEY = "0x7a-0x100000-0x6"
    changed = False
    for b in data.get("New Bookmarks", []):
        km = b.get("Keyboard Map", {})
        if KEY in km:
            del km[KEY]
            changed = True
            name = b.get("Name", "?")
            print(f"  {ok('removed from profile \"' + name + '\"')}")

    if changed:
        with open(ITERM2_PLIST, "wb") as f:
            plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)

# ── Diagnose ────────────────────────────────────────────────────────

def diagnose(env):
    print(f"\n  {bold('Diagnosing...')}\n")
    fixed = 0

    # Word segmentation
    if env["shell_name"] == "zsh":
        print(f"  {bold('Word Segmentation')}")
        checks = [
            ("paw.zsh exists", ZSH_WIDGET_PATH.exists(), lambda: _copy_zsh_widget()),
            ("paw.zsh in ~/.zshrc", _zshrc_has_paw(), lambda: _add_to_zshrc()),
            ("paw_segmenter.py exists", SEGMENTER_PATH.exists(), lambda: _copy_segmenter()),
            ("venv exists", VENV_DIR.exists(), lambda: _ensure_venv()),
            ("jieba importable", _jieba_importable(), lambda: _ensure_venv()),
        ]
        for label, passed, fix_fn in checks:
            if passed:
                print(f"  {ok(label)}")
            else:
                print(f"  {fail(label)}")
                if _prompt(f"Fix: {label}?"):
                    fix_fn()
                    fixed += 1

        pid = _daemon_pid()
        if pid:
            if _daemon_responsive():
                print(f"  {ok(f'daemon running and responsive (pid {pid})')}")
            else:
                print(f"  {warn(f'daemon running (pid {pid}) but not responsive')}")
                if _prompt("Fix: restart daemon?"):
                    daemon_restart()
                    fixed += 1
        else:
            print(f"  {fail('daemon not running')}")
            if _prompt("Fix: start daemon?"):
                _cleanup_stale_daemon()
                daemon_start()
                fixed += 1

        # Functional test
        if _daemon_responsive():
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect(str(SOCK_FILE))
                s.sendall("你好世界\t0\tnext_word\n".encode())
                r = s.recv(1024).decode().strip()
                s.close()
                if r == "2":
                    print(f"  {ok('segmentation test passed (jieba mode)')}")
                elif r == "1":
                    print(f"  {warn('segmentation test: fallback mode (jieba not loaded in daemon)')}")
                    if _prompt("Fix: restart daemon?"):
                        daemon_restart()
                        fixed += 1
                else:
                    print(f"  {fail(f'segmentation test unexpected: {r}')}")
            except Exception as e:
                print(f"  {fail(f'segmentation test error: {e}')}")
        print()

    # Image paste
    if env.get("has_iterm2"):
        print(f"  {bold('Image Paste (iTerm2)')}")
        api = _iterm2_api_enabled()
        print(f"  {ok('Python API enabled') if api else fail('Python API not enabled')}")
        if not api:
            print(f"    Settings (Cmd+,) → General → Magic → Enable Python API")

        plugin = (ITERM2_SCRIPTS / "paw.py").exists()
        print(f"  {ok('paw.py installed') if plugin else fail('paw.py not installed')}")
        if not plugin and _prompt("Fix: install plugin?"):
            enable_image_paste()
            fixed += 1

        link = ITERM2_AUTOLAUNCH / "paw.py"
        link_ok = link.exists() or link.is_symlink()
        if link_ok and link.is_symlink() and not link.resolve().exists():
            print(f"  {fail('AutoLaunch symlink broken')}")
            if _prompt("Fix: recreate symlink?"):
                link.unlink(missing_ok=True)
                link.symlink_to(ITERM2_SCRIPTS / "paw.py")
                print(f"  {ok('symlink recreated')}")
                fixed += 1
        elif link_ok:
            print(f"  {ok('AutoLaunch configured')}")
        else:
            print(f"  {fail('AutoLaunch not configured')}")
            if _prompt("Fix: configure AutoLaunch?"):
                ITERM2_AUTOLAUNCH.mkdir(parents=True, exist_ok=True)
                link.symlink_to(ITERM2_SCRIPTS / "paw.py")
                print(f"  {ok('symlink created')}")
                fixed += 1
        print()

    # Cmd+Z
    if env.get("has_iterm2"):
        print(f"  {bold('Cmd+Z Mapping')}")
        try:
            with open(ITERM2_PLIST, "rb") as f:
                data = plistlib.load(f)
            KEY = "0x7a-0x100000-0x6"
            unmapped = []
            for b in data.get("New Bookmarks", []):
                name = b.get("Name", "?")
                if KEY in b.get("Keyboard Map", {}):
                    print(f"  {ok(f'profile \"{name}\": mapped')}")
                else:
                    print(f"  {fail(f'profile \"{name}\": not mapped')}")
                    unmapped.append(name)
            if unmapped and _prompt("Fix: add mapping to unmapped profiles?"):
                enable_cmd_z()
                fixed += 1
        except Exception as e:
            print(f"  {fail(f'cannot check: {e}')}")
        print()

    if fixed:
        print(f"  {ok(f'{fixed} issue(s) fixed.')}")
    else:
        print(f"  {ok('All checks passed.')}")

def _prompt(msg):
    try:
        r = input(f"    → {msg} [Y/n] ").strip().lower()
        return r in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False

# ── Display ─────────────────────────────────────────────────────────

def print_header(env):
    print(f"\n  {bold(f'Paw v{VERSION}')}\n")

    print(f"  {bold('Environment')}")
    print(f"  {'─' * 48}")
    items = [
        ("OS", env["os"]),
        ("Shell", env["shell_version"]),
        ("Python", env["python"]),
        ("Terminal", f"{env['terminal']} {env['terminal_version']}".strip()),
    ]
    for label, value in items:
        print(f"  {label:<12}{value}")

    tools = []
    tools.append(ok("nc") if env["has_nc"] else fail("nc (required for word segmentation)"))
    if env["has_pngpaste"]:
        tools.append(ok("pngpaste"))
    else:
        tools.append(dim("pngpaste (optional, brew install pngpaste)"))
    print(f"  {'Tools':<12}{tools[0]}")
    for t in tools[1:]:
        print(f"  {'':<12}{t}")
    print()

def print_features(features, env):
    print(f"  {bold('Features')}")
    print(f"  {'─' * 56}")
    print(f"  {'#':<4}{'Feature':<28}{'Status':<12}{'Detail'}")
    print(f"  {'─' * 56}")

    visible = []
    for i, feat in enumerate(features, 1):
        if not feat.available(env):
            continue
        enabled, detail = feat.check()
        status = f"{GREEN}enabled{RESET}" if enabled else f"{RED}disabled{RESET}"
        print(f"  {i:<4}{feat.name:<28}{status:<21}{detail}")
        visible.append((i, feat))
    print()
    return visible

def interactive(features, env):
    while True:
        # Clear and redraw
        print_header(env)
        visible = print_features(features, env)

        try:
            cmd = input(f"  [{bold('n')}] toggle  [{bold('d')}] diagnose  [{bold('q')}] quit: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if cmd == "q":
            break
        elif cmd == "d":
            diagnose(env)
            input(f"\n  Press Enter to continue...")
        elif cmd.isdigit():
            n = int(cmd)
            match = [(i, f) for i, f in visible if i == n]
            if not match:
                print(f"  {fail('invalid number')}")
                continue
            _, feat = match[0]
            enabled, _ = feat.check()
            print()
            if enabled:
                print(f"  Disabling {bold(feat.name)}...")
                feat.disable()
            else:
                print(f"  Enabling {bold(feat.name)}...")
                feat.enable()
            input(f"\n  Press Enter to continue...")

# ── Main ────────────────────────────────────────────────────────────

def build_features():
    return [
        Feature(
            "word_jump", "Chinese word jump",
            check_word_jump, enable_word_seg, disable_word_seg,
        ),
        Feature(
            "word_delete", "Chinese word delete",
            check_word_delete, enable_word_seg, disable_word_seg,
        ),
        Feature(
            "image_paste", "Clipboard image paste",
            check_image_paste, enable_image_paste, disable_image_paste,
            requires_terminal="iterm2",
        ),
        Feature(
            "cmd_z", "Cmd+Z undo",
            check_cmd_z, enable_cmd_z, disable_cmd_z,
            requires_terminal="iterm2",
        ),
    ]

def main():
    env = detect_env()
    features = build_features()

    args = sys.argv[1:]

    if not args:
        interactive(features, env)
    elif args[0] == "status":
        print_header(env)
        print_features(features, env)
    elif args[0] == "diagnose":
        print_header(env)
        diagnose(env)
    elif args[0] == "daemon":
        if len(args) < 2:
            print("Usage: paw daemon [start|stop|restart|status]")
            return
        sub = args[1]
        if sub == "start":
            daemon_start()
        elif sub == "stop":
            daemon_stop()
        elif sub == "restart":
            daemon_restart()
        elif sub == "status":
            pid = _daemon_pid()
            if pid:
                resp = "responsive" if _daemon_responsive() else "not responsive"
                print(f"  {ok(f'running (pid {pid}, {resp})')}")
            else:
                print(f"  {fail('not running')}")
        else:
            print(f"Unknown daemon command: {sub}")
    else:
        print(f"Usage: paw [status|diagnose|daemon start|stop|restart]")

if __name__ == "__main__":
    main()
