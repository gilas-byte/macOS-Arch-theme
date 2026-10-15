#!/usr/bin/env bash
# Baixa o apple_cursor (versão e sha256 fixados no palette.toml) para ~/.local/share/icons
# se faltar, e aplica o cursor.
# Uso: apply.sh <tema> <url> <sha256>
set -euo pipefail
theme=${1:?uso: apply.sh <tema> <url> <sha256>} url=$2 sum=$3
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons"
if [[ "$theme" == macOS* && ! -d "$icons/$theme/cursors" ]]; then
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    echo "  baixando apple_cursor"
    curl -fsSL -o "$tmp/c.tar.xz" "$url"
    echo "$sum  $tmp/c.tar.xz" | sha256sum -c --quiet
    mkdir -p "$icons" && tar -xJf "$tmp/c.tar.xz" -C "$icons"
fi
plasma-apply-cursortheme "$theme"
