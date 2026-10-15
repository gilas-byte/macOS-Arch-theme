#!/usr/bin/env bash
# Troca o efeito de blur do KWin entre o Glass (luz na borda) e o better-blur-dx.
# Uso: ./blur-engine.sh glass | better-blur
# Depois é OBRIGATÓRIO logout/login: os dois são forks do mesmo efeito e, trocados com a
# sessão aberta, dividem a config interna e o blur some de tudo.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
case "${1:-}" in
glass)       glass=true  better=false translucency=false ;;
better-blur) glass=false better=true  translucency=true ;;
*) echo "uso: $0 glass | better-blur" >&2; exit 1 ;;
esac
python3 - "$better" "$glass" "$translucency" <<'PY'
import re, sys
better, glass, transl = sys.argv[1:]
p = "palette.toml"; s = open(p).read()
s = re.sub(r"\[effects\]\nbetter_blur = \w+\nglass = \w+\ntranslucency = \w+",
           f"[effects]\nbetter_blur = {better}\nglass = {glass}\ntranslucency = {transl}", s)
open(p, "w").write(s)
PY
./install.sh --only blur,glass
echo
echo ">>> Agora faça LOGOUT e LOGIN. Sem isso o blur não funciona direito."
