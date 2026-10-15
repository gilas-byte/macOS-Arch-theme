#!/usr/bin/env bash
# Ponte entre o tooling (roda como usuário) e o apply.sh (precisa de root).
# Num terminal, pede a senha do sudo; sem terminal, só mostra o comando a rodar.
# Uso: state.sh <tema> <id>
set -euo pipefail
cmd=(targets/plymouth/apply.sh "$1" "$2")
if [[ -t 0 ]]; then
    sudo "${cmd[@]}"
else
    echo "  Plymouth precisa de sudo. Rode num terminal, na raiz do repo:"
    echo "    sudo ${cmd[*]}"
fi
