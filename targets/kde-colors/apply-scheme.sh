#!/usr/bin/env bash
# plasma-apply-colorscheme recusa reaplicar o esquema atual; alterna por outro antes para
# que mudanças no arquivo .colors cheguem ao kdeglobals.
set -euo pipefail
scheme=${1:?uso: apply-scheme.sh <esquema>}
current=$(kreadconfig6 --file kdeglobals --group General --key ColorScheme)
if [[ "$current" == "$scheme" ]]; then
    other=BreezeDark
    [[ "$scheme" == BreezeDark ]] && other=BreezeLight
    plasma-apply-colorscheme "$other" >/dev/null
fi
plasma-apply-colorscheme "$scheme"
