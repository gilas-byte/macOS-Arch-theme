#!/usr/bin/env bash
# get: imprime a opacidade dos painéis (um valor se todos iguais, senão JSON id->valor).
# set VALOR: aplica um valor a todos os painéis, ou um JSON id->valor (usado no restore).
set -euo pipefail
shell() { qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$1"; }
case "${1:-}" in
    get)
        shell 'var o = {}, v = [];
               panels().forEach(function (p) { o[p.id] = p.opacity; if (v.indexOf(p.opacity) < 0) v.push(p.opacity); });
               print(v.length == 1 ? v[0] : JSON.stringify(o));' ;;
    set)
        value=${2:?uso: panel-opacity.sh set <valor>}
        [[ "$value" =~ ^[a-z]+$|^\{[\"0-9a-z:,]*\}$ ]] || { echo "valor inválido: $value" >&2; exit 1; }
        shell "var v = '$value', m = v.charAt(0) == '{' ? JSON.parse(v) : null;
               panels().forEach(function (p) { var x = m ? m[p.id] : v; if (x) p.opacity = x; });" ;;
    *) echo "uso: panel-opacity.sh get|set <valor>" >&2; exit 1 ;;
esac
