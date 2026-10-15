#!/usr/bin/env bash
# Instala o Kvantum do MacTahoe de vendor/ em ~/.config/Kvantum (se faltar) e escolhe o tema.
# Uso: apply.sh <tema>   (ex.: MacTahoeDark, que fica na pasta MacTahoe)
set -euo pipefail
theme=${1:?uso: apply.sh <tema>}
kv="${XDG_CONFIG_HOME:-$HOME/.config}/Kvantum"
if [[ "$theme" == MacTahoe* && ! -f "$kv/MacTahoe/$theme.kvconfig" ]]; then
    mkdir -p "$kv" && cp -r vendor/MacTahoe-kde/Kvantum/MacTahoe "$kv/"
fi
kwriteconfig6 --file "$kv/kvantum.kvconfig" --group General --key theme "$theme"
