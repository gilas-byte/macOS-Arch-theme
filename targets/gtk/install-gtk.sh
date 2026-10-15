#!/usr/bin/env bash
# Instala o MacTahoe-gtk-theme (só a variante escura, opacidade normal) de vendor/ em ~/.themes.
# Uso: install-gtk.sh <tema>   (ex.: MacTahoe-Dark)
set -euo pipefail
theme=${1:?uso: install-gtk.sh <tema>}
[[ -d "$HOME/.themes/$theme/gtk-4.0" ]] && exit 0
echo "  instalando MacTahoe-gtk-theme de vendor/ em ~/.themes"
(cd vendor/MacTahoe-gtk-theme && ./install.sh -c dark -o normal >/dev/null)
[[ -d "$HOME/.themes/$theme/gtk-4.0" ]] || { echo "  $theme não apareceu em ~/.themes" >&2; exit 1; }
