#!/usr/bin/env bash
# Wallpaper da área de trabalho (todas as telas).
# get: imprime a imagem atual (só o nome, se for pacote em ~/.local/share/wallpapers). set <valor>: nome de pacote em ~/.local/share/wallpapers
# (instalado de vendor/MacTahoe-kde se faltar) ou caminho/URL de imagem.
set -euo pipefail
action=$1 value=${2:-}
walls="${XDG_DATA_HOME:-$HOME/.local/share}/wallpapers"
case $action in
get)
    img=$(grep -m1 '^Image=' "${XDG_CONFIG_HOME:-$HOME/.config}/plasma-org.kde.plasma.desktop-appletsrc" | cut -d= -f2- || true)
    # Pacote em ~/.local/share/wallpapers vira só o nome, para comparar com o palette.toml.
    rel=${img#file://}; rel=${rel#"$walls/"}
    if [[ "$rel" != "${img#file://}" ]]; then echo "${rel%%/*}"; else echo "$img"; fi ;;
set)
    [[ -n "$value" ]] || exit 0
    if [[ "$value" != */* ]]; then
        if [[ ! -d "$walls/$value" ]]; then
            mkdir -p "$walls" && cp -r "vendor/MacTahoe-kde/wallpapers/$value" "$walls/"
        fi
        value="$walls/$value"
    fi
    plasma-apply-wallpaperimage "${value#file://}" ;;
esac
