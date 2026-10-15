#!/usr/bin/env bash
# Instala o look-and-feel do MacTahoe de vendor/ (se faltar) e escolhe o splash dele.
# Uso: apply.sh <pacote>   (valor vazio ou "None" desliga o splash)
set -euo pipefail
pkg=${1:-None}
lnf="${XDG_DATA_HOME:-$HOME/.local/share}/plasma/look-and-feel"
if [[ "$pkg" == com.github.vinceliuice.MacTahoe* && ! -d "$lnf/$pkg" ]]; then
    mkdir -p "$lnf" && cp -r "vendor/MacTahoe-kde/plasma/look-and-feel/$pkg" "$lnf/"
fi
engine=KSplashQML
[[ "$pkg" == None ]] && engine=none
kwriteconfig6 --file ksplashrc --group KSplash --key Engine "$engine"
kwriteconfig6 --file ksplashrc --group KSplash --key Theme "$pkg"
