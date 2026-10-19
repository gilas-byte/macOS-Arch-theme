#!/usr/bin/env bash
# Prova que o alvo cursor-effects pede recompilação quando o KWin muda de versão,
# mesmo sem o código do plugin mudar (o KWin só carrega plugin da versão exata dele).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

export XDG_STATE_HOME TAHOE_CURSOR_SO
XDG_STATE_HOME=$(mktemp -d)
TAHOE_CURSOR_SO="$XDG_STATE_HOME/tahoecursor.so"
trap 'rm -rf "$XDG_STATE_HOME"' EXIT
touch "$TAHOE_CURSOR_SO"
mkdir -p "$XDG_STATE_HOME/t"

pass() { echo "PASSOU: $*"; }
fail() { echo "FALHOU: $*" >&2; exit 1; }
get() { targets/cursor-effects/state.sh get t; }

KWIN_VERSION=6.8.0 targets/cursor-effects/state.sh stamp t >"$XDG_STATE_HOME/t/tahoecursor.sha256"
[[ $(KWIN_VERSION=6.8.0 get) == atualizado ]] || fail "mesmo código e mesmo KWin deveria estar atualizado"
pass "mesmo código e mesmo KWin: atualizado"

[[ $(KWIN_VERSION=6.9.0 get) == desatualizado ]] || fail "KWin novo deveria pedir recompilação"
pass "KWin novo: desatualizado"

[[ $(KWIN_VERSION=6.8.0 targets/cursor-effects/state.sh stamp t) != $(KWIN_VERSION=6.9.0 targets/cursor-effects/state.sh stamp t) ]] \
    || fail "carimbo não depende da versão do KWin"
pass "carimbo muda com a versão do KWin"

rm "$TAHOE_CURSOR_SO"
[[ $(KWIN_VERSION=6.8.0 get) == ausente ]] || fail "sem o .so deveria ser ausente"
pass "sem o .so: ausente"
