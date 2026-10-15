#!/usr/bin/env bash
# SF Pro + SF Mono baixadas do site da Apple para ~/.local/share/fonts/<id>-apple.
# A licença da Apple não permite redistribuir, então o repo nunca guarda os arquivos.
# Uso: apple-fonts.sh get|set|restore <id> <url-base> [valor]
set -euo pipefail
action=$1 id=$2 base=$3 value=${4:-}
dir="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/${id}-apple"

case $action in
get)
    [[ -f "$dir/.installed" ]] && echo installed || true ;;
set|restore)
    if [[ "$value" != installed ]]; then
        rm -rf "$dir"
        fc-cache -f >/dev/null 2>&1 || true
        exit 0
    fi
    [[ -f "$dir/.installed" ]] && exit 0
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    for name in SF-Pro SF-Mono; do
        echo "  baixando $name.dmg da Apple"
        curl -fsSL -o "$tmp/$name.dmg" "$base/$name.dmg"
        7z x -y -o"$tmp/$name/dmg" "$tmp/$name.dmg" >/dev/null
        pkg=$(find "$tmp/$name/dmg" -name '*.pkg' -maxdepth 2 | head -1)
        7z x -y -o"$tmp/$name/pkg" "$pkg" >/dev/null
        for payload in $(find "$tmp/$name/pkg" -name Payload -type f); do
            7z x -y -so "$payload" > "$tmp/$name/payload.cpio"
            7z x -y -o"$tmp/$name/files" "$tmp/$name/payload.cpio" >/dev/null
        done
    done
    mkdir -p "$dir"
    find "$tmp" -path '*/files/*' \( -name '*.otf' -o -name '*.ttf' \) -exec cp {} "$dir/" \;
    count=$(find "$dir" -type f | wc -l)
    (( count > 0 )) || { echo "nenhuma fonte extraída" >&2; exit 1; }
    touch "$dir/.installed"
    fc-cache -f "$dir" >/dev/null
    echo "  $count arquivos de fonte em $dir" ;;
esac
