#!/usr/bin/env bash
# Dolphin com cara de Finder.
#   view get | view set <n>          modo de exibição global (0 ícones, 1 detalhes, 2 compacto),
#                                    guardado no xattr da pasta view_properties/global
#   group get <Grupo> | group set <Grupo> <true|false>
#                                    esconde/mostra uma seção da sidebar (user-places.xbel)
set -euo pipefail
data="${XDG_DATA_HOME:-$HOME/.local/share}"
global="$data/dolphin/view_properties/global"
xbel="$data/user-places.xbel"
attr="user.kde.fm.viewproperties#1"

read_props() { getfattr --only-values -n "$attr" "$global" 2>/dev/null || true; }

case "$1 $2" in
"view get")
    read_props | sed -n 's/^ViewMode=//p' ;;
"view set")
    value=${3:?valor}
    [[ -n "$value" ]] || value=1
    mkdir -p "$global"
    props=$(read_props)
    [[ -n "$props" ]] || props=$'[Dolphin]\nVersion=4'
    if grep -q '^ViewMode=' <<<"$props"; then
        props=$(sed "s/^ViewMode=.*/ViewMode=$value/" <<<"$props")
    else
        props=$(sed "s/^\[Dolphin\]$/[Dolphin]\nViewMode=$value/" <<<"$props")
    fi
    setfattr -n "$attr" -v "$props" "$global" ;;
"group get")
    grep -oP "(?<=<GroupState-$3-IsHidden>)(true|false)" "$xbel" 2>/dev/null || true ;;
"group set")
    group=$3 value=${4:-false}
    [[ -f "$xbel" ]] || exit 0
    python3 - "$xbel" "$group" "$value" <<'PY'
import re, sys
path, group, value = sys.argv[1:]
tag = f"GroupState-{group}-IsHidden"
text = open(path).read()
new, n = re.subn(f"<{tag}>(true|false)</{tag}>", f"<{tag}>{value}</{tag}>", text)
if n == 0:
    raise SystemExit(f"{tag} não encontrado em {path}")
if new != text:
    open(path, "w").write(new)
PY
    ;;
*) echo "uso: dolphin.sh view get|set <n> | group get|set <Grupo> [true|false]" >&2; exit 1 ;;
esac
