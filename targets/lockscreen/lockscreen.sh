#!/usr/bin/env bash
# Wallpaper da tela de bloqueio.
#   get        imprime a imagem (só o nome, se for pacote em ~/.local/share/wallpapers)
#   set <v>    nome de pacote em ~/.local/share/wallpapers, ou caminho/URL de imagem
set -euo pipefail
action=$1 value=${2:-}
walls="${XDG_DATA_HOME:-$HOME/.local/share}/wallpapers"
k=(--file kscreenlockerrc --group Greeter --group Wallpaper --group org.kde.image --group General --key Image)
case $action in
get)
    img=$(kreadconfig6 "${k[@]}")
    rel=${img#file://}; rel=${rel#"$walls/"}
    if [[ -n "$img" && "$rel" != "${img#file://}" ]]; then echo "${rel%%/*}"; else echo "$img"; fi ;;
set)
    if [[ -z "$value" ]]; then
        kwriteconfig6 "${k[@]}" --delete
        exit 0
    fi
    [[ "$value" == */* ]] || value="file://$walls/$value"
    kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin org.kde.image
    kwriteconfig6 "${k[@]}" "$value" ;;
esac
