#!/usr/bin/env bash
# Install the JoyToKey replacement so it works without this clone.
#   ./install.sh              copy files to ~/.local/share/joytokey and link joytokey + with-joytokey into ~/.local/bin
#   ./install.sh --uninstall  remove them
# Re-run after `git pull` to update the installed copy.
set -euo pipefail

src="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/JoyToKey"
share="${XDG_DATA_HOME:-$HOME/.local/share}/joytokey"
bin="$HOME/.local/bin"
link="$bin/with-joytokey"
daemon_link="$bin/joytokey"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$link" "$daemon_link"
    rm -rf "$share"
    echo "Removed $link, $daemon_link and $share"
    exit 0
fi
if [[ $# -gt 0 ]]; then echo "usage: ${0##*/} [--uninstall]" >&2; exit 2; fi

for f in joytokey.py joytokey_cfg.py with-joytokey; do
    [[ -f "$src/$f" ]] || { echo "missing $src/$f" >&2; exit 1; }
done

mkdir -p "$share" "$bin"
install -m 755 "$src/joytokey.py" "$src/with-joytokey" "$share/"
install -m 644 "$src/joytokey_cfg.py" "$share/"
mkdir -p "$share/profiles"
install -m 644 "$src"/profiles/*.toml "$share/profiles/"
ln -sfn "$share/with-joytokey" "$link"
ln -sfn "$share/joytokey.py" "$daemon_link"
echo "Installed to $share"
echo "Linked $link and $daemon_link"

# --- checks (warnings only) ---
python3 -c "import evdev" 2>/dev/null || echo "WARNING: python-evdev not found (CachyOS/Arch: sudo pacman -S python-evdev)" >&2
[[ -w /dev/uinput ]] || echo "WARNING: /dev/uinput is not writable by you; needs a udev rule/ACL or the 'input' group" >&2
case ":$PATH:" in *":$bin:"*) ;; *) echo "NOTE: $bin is not on your PATH" >&2 ;; esac
echo "Profiles: $share/profiles (copy one to ~/.config/joytokey/config.toml to customise)"
echo "Try: with-joytokey --config FILE.cfg <command>   (daemon options: joytokey --help)"
