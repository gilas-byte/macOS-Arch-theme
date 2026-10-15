#!/usr/bin/env bash
# Prova da fundação: render, dry-run, idempotência, backup e restore
# usando o alvo _selftest em /tmp. O estado de backup vai para um diretório temporário.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

ID=$(python3 -c 'import tomllib; print(tomllib.load(open("palette.toml","rb"))["theme"]["id"])')
DIR="/tmp/${ID}-selftest"
export XDG_STATE_HOME
XDG_STATE_HOME=$(mktemp -d)
trap 'rm -rf "$XDG_STATE_HOME"' EXIT

pass() { echo "PASSOU: $*"; }
fail() { echo "FALHOU: $*" >&2; exit 1; }
snapshot() {
    find "$DIR" -printf '%P %y %l\n' | sort
    find "$DIR" -type f -exec md5sum {} + | sort
}

rm -rf "$DIR"
mkdir -p "$DIR"
printf 'linha do usuario = 1\n' > "$DIR/host.conf"
printf "@import 'colors.css';" > "$DIR/host.css"
printf '[General]\nfont=Hack,11,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n' > "$DIR/test.rc"
before=$(snapshot)

./install.sh --only _selftest --dry-run >/dev/null
[[ "$(snapshot)" == "$before" ]] || fail "dry-run alterou arquivos"
[[ ! -d "$XDG_STATE_HOME/$ID" ]] || fail "dry-run criou backup"
pass "dry-run não altera nada"

./install.sh --only _selftest >/dev/null
after_first=$(snapshot)
[[ "$after_first" != "$before" ]] || fail "install não mudou nada"
grep -q '^background = #' build/_selftest/sample.conf || fail "render de cor"
grep -q '^dollar = \$literal$' build/_selftest/sample.conf || fail "escape de \$\$"
! grep -q '\${' build/_selftest/sample.svg || fail "svg com placeholder sobrando"
grep -q 'rx="10"' "$DIR/sample.svg" || fail "svg renderizado/copiado"
[[ -L "$DIR/sample.conf" ]] || fail "symlink"
grep -q '^linha do usuario = 1$' "$DIR/host.conf" || fail "managed-block apagou conteúdo do usuário"
grep -q '>>> '"$ID"' >>>' "$DIR/host.conf" || fail "managed-block ausente"
head -1 "$DIR/host.css" | grep -q "@import 'colors.css';" || fail "after-imports"
grep -q '^font=SF Pro Text,11,' "$DIR/test.rc" || fail "troca de família mantendo tamanho"
grep -q '^Accent=10,132,255$' "$DIR/test.rc" || fail "kwrite em grupo aninhado"
[[ "$(cat "$DIR/state")" == "${ID}-on" ]] || fail "state"
backups=$(find "$XDG_STATE_HOME/$ID/backups" -name manifest.json | wc -l)
[[ "$backups" == 1 ]] || fail "esperado 1 backup, achei $backups"
pass "install aplica render, symlink, copy, svg, managed-block, kwrite e state"

out=$(./install.sh --only _selftest)
[[ "$(snapshot)" == "$after_first" ]] || fail "segunda execução alterou arquivos"
grep -q 'sem mudanças' <<<"$out" || fail "segunda execução reportou mudanças"
grep -q 'post do _selftest' <<<"$out" && fail "post rodou sem mudanças"
backups=$(find "$XDG_STATE_HOME/$ID/backups" -name manifest.json | wc -l)
[[ "$backups" == 1 ]] || fail "segunda execução criou backup"
pass "idempotente"

./uninstall.sh >/dev/null
[[ "$(snapshot)" == "$before" ]] || { diff <(echo "$before") <(snapshot) || true; fail "restore não voltou ao estado original"; }
pass "uninstall restaura o estado original byte a byte"

sum_build() { find build/_selftest -type f -exec md5sum {} + | sort; }
built=$(sum_build)
./install.sh --only _selftest --profile _selftest --dry-run >/dev/null
[[ "$(sum_build)" == "$built" ]] || fail "dry-run com perfil mudou build/ (que o sistema lê por symlink)"
[[ ! -e "$XDG_STATE_HOME/$ID/profile" ]] || fail "dry-run gravou o perfil"
pass "dry-run com perfil não toca em build/ nem grava o perfil"

out=$(./uninstall.sh)
grep -q 'Nada para restaurar' <<<"$out" || fail "restore repetido"
pass "uninstall repetido é seguro"

rm -rf "$DIR"

echo "Selftest OK."
