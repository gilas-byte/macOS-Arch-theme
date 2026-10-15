#!/usr/bin/env bash
# Layout do Plasma (barra de menu + Dock).
#   get              imprime "applied" se o layout do tema foi aplicado
#   set applied      guarda uma cópia do layout atual (só na primeira vez) e roda o layout.js
#   restore <valor>  valor vazio: devolve a cópia guardada e reinicia o plasmashell
# O layout fica num arquivo que o Plasma reescreve o tempo todo, então o backup é a cópia
# inteira, feita antes da primeira mudança.
set -euo pipefail
action=$1 id=$2 value=${3:-}
cfg="${XDG_CONFIG_HOME:-$HOME/.config}"
dir="${XDG_STATE_HOME:-$HOME/.local/state}/$id/layout"
files=(plasma-org.kde.plasma.desktop-appletsrc plasmashellrc)
shell() { qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$1"; }

case $action in
get)
    [[ -f "$dir/applied" ]] && echo applied || true ;;
set)
    if [[ ! -d "$dir/saved" ]]; then
        mkdir -p "$dir/saved"
        for f in "${files[@]}"; do [[ -f "$cfg/$f" ]] && cp "$cfg/$f" "$dir/saved/"; done
    fi
    out=$(shell "$(cat build/layout/layout.js)")
    [[ "$out" == *"layout ok"* ]] || { echo "  layout.js falhou: $out" >&2; exit 1; }
    touch "$dir/applied" ;;
restore)
    [[ -z "$value" && -d "$dir/saved" ]] || exit 0
    kquitapp6 plasmashell >/dev/null 2>&1 || true
    for f in "${files[@]}"; do [[ -f "$dir/saved/$f" ]] && cp "$dir/saved/$f" "$cfg/$f"; done
    (setsid kstart plasmashell >/dev/null 2>&1 &)
    rm -rf "$dir" ;;
esac
