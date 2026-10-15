#!/usr/bin/env bash
# Instala o MacTahoe-icon-theme de vendor/ em ~/.local/share/icons (se faltar) e aplica o tema.
# Uso: apply.sh <tema>
set -euo pipefail
theme=${1:?uso: apply.sh <tema>}
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons"
if [[ "$theme" == MacTahoe* && ! -d "$icons/$theme" ]]; then
    echo "  instalando MacTahoe-icon-theme de vendor/"
    (cd vendor/MacTahoe-icon-theme && ./install.sh -d "$icons" >/dev/null)
fi
/usr/lib/plasma-changeicons "$theme"
