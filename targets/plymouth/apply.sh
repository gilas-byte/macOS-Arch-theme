#!/usr/bin/env bash
# Troca o tema do Plymouth (precisa de root: escreve em /usr/share e refaz o initramfs).
# Uso: sudo targets/plymouth/apply.sh <tema> <id-do-tahoe>
#   <tema> = id do tahoe: instala build/plymouth/theme em /usr/share/plymouth/themes/<id>
#   outro tema (ex.: cachyos): volta para ele e apaga o tema do tahoe
# Rode da raiz do repo, depois de ./install.sh (que renderiza build/plymouth).
set -euo pipefail
theme=${1:?uso: apply.sh <tema> <id>} id=${2:?uso: apply.sh <tema> <id>}
[[ $EUID -eq 0 ]] || { echo "precisa de root: sudo $0 $*" >&2; exit 1; }
dest=/usr/share/plymouth/themes/$id

if [[ "$theme" == "$id" ]]; then
    src=build/plymouth/theme
    [[ -f "$src/theme.script" ]] || { echo "falta $src: rode ./install.sh antes" >&2; exit 1; }
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    for svg in "$src"/*.svg; do
        rsvg-convert "$svg" -o "$tmp/$(basename "${svg%.svg}").png"
    done
    cp "$src/theme.plymouth" "$tmp/$id.plymouth"
    cp "$src/theme.script" "$tmp/$id.script"
    rm -rf "$dest" && install -d -m 755 "$dest" && install -m 644 "$tmp"/* "$dest/"
fi

echo "Tema do Plymouth: $(plymouth-set-default-theme) -> $theme (refazendo o initramfs, ~1 min)"
plymouth-set-default-theme -R "$theme"
[[ "$theme" == "$id" ]] || rm -rf "$dest"
echo "Pronto. Aparece no próximo boot."
