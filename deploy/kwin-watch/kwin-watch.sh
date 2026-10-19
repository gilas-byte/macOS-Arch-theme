#!/usr/bin/env bash
# Vigia de update do KWin (roda como USUÁRIO, disparado pelo kwin-watch.path; sem sudo).
# Fluxo: o KWin mudou de versão? -> recompila o tahoecursor (determinístico) -> confere -> se falhar,
# chama o Claude Code (haiku) pra tentar consertar o código -> confere de novo -> manda UMA mensagem no
# Telegram montada a partir dos testes REAIS (nunca do relato do agente).
# O blur (better_blur_dx, AUR) precisa de sudo pra reinstalar: o vigia só avisa o comando.
# Variáveis de teste: TAHOE_NO_WAIT=1 (não espera o pacman), TAHOE_FORCE=1 (ignora "já tratei esta versão"),
# TAHOE_FORCE_AGENT=1 (chama o haiku mesmo sem falha), TAHOE_TEST=1 (marca a mensagem como teste).
set -u
REPO="${TAHOE_REPO:-$HOME/Documents/tahoe-theme}"
STATE="$HOME/.local/state/tahoe"; mkdir -p "$STATE"
HANDLED="$STATE/kwin-handled-version"; LOG="$STATE/kwin-watch.log"
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T') kwin-watch começou"

if [[ -z ${TAHOE_NO_WAIT:-} ]]; then
    for _ in $(seq 1 120); do [[ -e /var/lib/pacman/db.lck ]] || break; sleep 5; done
    sleep 45   # deixa a transação terminar de gravar
fi

cur=$(pacman -Q kwin 2>/dev/null | awk '{print $2}' | sed -E 's/^[0-9]+://; s/-[0-9.]+$//')
[[ -n $cur ]] || { echo "sem kwin instalado"; exit 0; }
old=$(cat "$HANDLED" 2>/dev/null || true)
if [[ -z $old ]]; then echo "$cur" >"$HANDLED"; echo "primeira execução: guardei $cur"; exit 0; fi
if [[ $old == "$cur" && -z ${TAHOE_FORCE:-} ]]; then echo "KWin continua $cur: nada a fazer"; exit 0; fi

cd "$REPO" || exit 1
export TMPDIR="${TMPDIR:-/tmp}"
tag=""; [[ -n ${TAHOE_TEST:-} ]] && tag="[TESTE] "
used_agent=no
head_before=$(git rev-parse HEAD)
check() { KWIN_CHECK_ONLY=tahoecursor tests/kwin-check.sh --compile; }

echo "KWin $old -> $cur: recompilando o tahoecursor"
./install.sh --only cursor-effects || true
if check >"$STATE/check1.txt" 2>&1 && [[ -z ${TAHOE_FORCE_AGENT:-} ]]; then
    echo "check ok sem agente"
else
    echo "chamando o haiku"; used_agent=yes
    prompt=$(cat <<EOF
O KWin foi atualizado de $old para $cur. O plugin do cursor (effects/tahoecursor, C++) deste repositório pode ter parado de compilar ou de funcionar.
Saída do teste agora:
$(cat "$STATE/check1.txt")

Sua tarefa, nesta ordem:
1. Rode: KWIN_CHECK_ONLY=tahoecursor tests/kwin-check.sh --compile. Se tudo passa (ou só há "PENDENTE"), não mude código algum; responda "nada a corrigir".
2. Se não compila, leia os erros e corrija SÓ os arquivos em effects/tahoecursor/ (a API do KWin muda entre versões; os headers estão em /usr/include/kwin). Veja git log -5 -p -- effects/tahoecursor para um exemplo de port anterior. Mudanças mínimas.
3. Rode ./install.sh --only cursor-effects e depois tests/kwin-nested.sh. Os dois precisam passar.
4. Só se tudo passar: git add dos arquivos alterados e UM commit em português ("tahoecursor: porta para o KWin $cur ..."). Se NÃO passar: desfaça com git checkout -- effects/ (não deixe código quebrado) e explique o que impediu.
Regras: sem sudo, sem rede, nada fora de $REPO e /tmp, sem push, não mexa em outros alvos do tema. Responda em 3 linhas: o que mudou e o resultado real dos testes.
EOF
)
    timeout 1500 claude -p --model haiku --max-turns 60 --max-budget-usd 5 --output-format text \
        --allowedTools "Read,Edit,Write,Bash(tests/kwin-check.sh*),Bash(KWIN_CHECK_ONLY=tahoecursor tests/kwin-check.sh*),Bash(tests/kwin-nested.sh),Bash(./install.sh --only cursor-effects*),Bash(git add effects/tahoecursor/*),Bash(git commit *),Bash(git status*),Bash(git diff*),Bash(git log*),Bash(git checkout -- effects/*),Bash(grep *),Bash(ls *),Bash(cat *),Bash(cmake *)" \
        <<<"$prompt" >"$STATE/agent-out.txt" 2>&1
    echo "agente terminou rc=$?"; tail -c 1500 "$STATE/agent-out.txt"
fi

# Verificação final pelos testes, não pelo agente
res_cursor=ok; reason=""
check >"$STATE/check2.txt" 2>&1 || { res_cursor=falhou; reason=$(grep -E "FALHOU|error" "$STATE/check2.txt" | head -3 | cut -c1-220); }
if [[ $res_cursor == ok ]] && ! tests/kwin-nested.sh >"$STATE/nested.txt" 2>&1; then
    res_cursor=falhou; reason=$(grep FALHOU "$STATE/nested.txt" | head -2)
fi
blur=ok
KWIN_CHECK_ONLY=better_blur_dx tests/kwin-check.sh >"$STATE/check-blur.txt" 2>&1 || blur=velho

msg="${tag}KWin atualizou: $old -> $cur."
if [[ $res_cursor == ok ]]; then
    msg+=$'\nCursor (tahoecursor): pronto, compilado pra '"$cur"$' e carregando num KWin de teste.'
    [[ $(git rev-parse HEAD) != "$head_before" ]] && msg+=$'\nO haiku portou o código e commitou: '"$(git log -1 --format=%s)"
    msg+=$'\nFaça logout/login pra ele entrar na sua sessão.'
else
    msg+=$'\nCursor (tahoecursor): NÃO resolvido.\n'"$reason"$'\nLog: ~/.local/state/tahoe/kwin-watch.log (precisa de port manual; me chama).'
fi
if [[ $blur == velho ]]; then
    msg+=$'\nBlur (better_blur_dx): o pacote do AUR ainda é da versão antiga. Rode no terminal: paru -S kwin-effects-better-blur-dx (precisa de sudo). Se o AUR ainda não saiu pra '"$cur"$', o blur some até sair.'
else
    msg+=$'\nBlur: ok.'
fi
[[ $res_cursor == ok ]] && echo "$cur" >"$HANDLED"   # se falhou, tenta de novo no próximo disparo
echo "$msg"
hermes send -t telegram "$msg" || echo "hermes send falhou"
