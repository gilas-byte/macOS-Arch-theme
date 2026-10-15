#!/usr/bin/env bash
# Uso: apply.sh <tema>
# O plasma-apply-desktoptheme recusa reaplicar o tema ativo. Quando o conteúdo do tema muda
# sem o nome mudar, passa um instante pelo Breeze para o plasmashell recarregar os SVGs.
set -euo pipefail
theme=${1:?uso: apply.sh <tema>}
current=$(kreadconfig6 --file plasmarc --group Theme --key name)
if [[ "$current" == "$theme" ]]; then
    plasma-apply-desktoptheme default >/dev/null
fi
exec plasma-apply-desktoptheme "$theme"
