#!/usr/bin/env bash
# Checa se os plugins C++ do KWin (blur e efeitos de cursor) ainda servem para o KWin instalado.
# Só lê; nunca instala nem usa sudo.
#   tests/kwin-check.sh            versão dos plugins x KWin + carregados na sessão
#   tests/kwin-check.sh --compile  também compila tahoecursor em /tmp contra os headers atuais
#                                  (acha quebra de API do KWin antes do logout)
# KWIN_CHECK_ONLY=<id> limita a checagem a um plugin (tahoecursor ou better_blur_dx).
# Saída: 0 = tudo ok, 1 = algum plugin precisa de rebuild/reinstalação, 2 = erro do próprio teste.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

# O plugin do usuário (instalado sem sudo, achado via QT_PLUGIN_PATH) vale mais que o do sistema.
USERPLUG="$HOME/.local/lib/qt6/plugins/kwin/effects/plugins"
PLUGDIR=/usr/lib/qt6/plugins/kwin/effects/plugins
find_so() { if [[ -f $USERPLUG/$1 ]]; then echo "$USERPLUG/$1"; else echo "$PLUGDIR/$1"; fi; }
# id do efeito : arquivo .so : como consertar
PLUGINS=(
    "tahoecursor:tahoecursor.so:./install.sh --only cursor-effects"
    "better_blur_dx:better_blur_dx.so:paru -S kwin-effects-better-blur-dx  (ou yay)"
)

rc=0
ok()   { echo "PASSOU: $*"; }
bad()  { echo "FALHOU: $*" >&2; rc=1; }

kwin_ver=$(pacman -Q kwin 2>/dev/null | awk '{print $2}' | sed -E 's/^[0-9]+://; s/-[0-9.]+$//')
[[ -n $kwin_ver ]] || { echo "erro: pacote kwin não encontrado" >&2; exit 2; }
echo "KWin instalado: $kwin_ver"

for entry in "${PLUGINS[@]}"; do
    IFS=: read -r id file fix <<<"$entry"
    [[ -n ${KWIN_CHECK_ONLY:-} && $id != "$KWIN_CHECK_ONLY" ]] && continue
    so=$(find_so "$file")
    if [[ ! -f $so ]]; then
        bad "$id: plugin não instalado ($so). Conserto: $fix"
        continue
    fi
    built=$(grep -a -o 'org\.kde\.kwin\.EffectPluginFactory[0-9][0-9.]*' "$so" | head -1 | sed 's/.*Factory//')
    if [[ -z $built ]]; then
        bad "$id: não achei a versão do KWin gravada no plugin"
    elif [[ $built == "$kwin_ver" ]]; then
        ok "$id compilado para o KWin $built"
    else
        bad "$id foi compilado para o KWin $built, mas o instalado é $kwin_ver. Conserto: $fix"
    fi
done

# Carregados na sessão (precisa de KWin rodando e qdbus6)
if command -v qdbus6 >/dev/null && qdbus6 org.kde.KWin /KWin >/dev/null 2>&1; then
    for entry in "${PLUGINS[@]}"; do
        IFS=: read -r id file fix <<<"$entry"
        [[ -n ${KWIN_CHECK_ONLY:-} && $id != "$KWIN_CHECK_ONLY" ]] && continue
        enabled=$(kreadconfig6 --file kwinrc --group Plugins --key "${id}Enabled" 2>/dev/null)
        [[ $enabled == true ]] || { echo "PULOU: $id (desligado no kwinrc)"; continue; }
        if [[ $(qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.isEffectLoaded "$id" 2>/dev/null) == true ]]; then
            ok "$id carregado no KWin em execução"
        else
            so=$(find_so "$file")
            kpid=$(pgrep -x kwin_wayland | head -1)
            kstart=$(date -d "$(ps -o lstart= -p "$kpid" 2>/dev/null)" +%s 2>/dev/null || echo 0)
            if [[ -f $so && $(stat -c %Y "$so") -gt $kstart && $(grep -a -o 'EffectPluginFactory[0-9][0-9.]*' "$so" | head -1 | sed 's/.*Factory//') == "$kwin_ver" ]]; then
                echo "PENDENTE: $id está instalado e atual, mas o KWin em execução é mais velho que ele. Faça logout/login."
            else
                bad "$id está ligado no kwinrc mas NÃO carregou no KWin. Conserto: $fix e depois logout/login"
            fi
        fi
    done
else
    echo "PULOU: KWin não está rodando nesta sessão (checagem de carregamento)"
fi

# Compila contra os headers atuais: pega quebra de API (ex.: paintScreen mudou de void para bool no 6.8)
if [[ ${1:-} == --compile && ( -z ${KWIN_CHECK_ONLY:-} || ${KWIN_CHECK_ONLY} == tahoecursor ) ]]; then
    b=$(mktemp -d "${TMPDIR:-/tmp}/tahoecursor-check.XXXXXX")
    trap 'rm -rf "$b"' EXIT
    if cmake -S effects/tahoecursor -B "$b" -DCMAKE_BUILD_TYPE=Release >"$b/cmake.log" 2>&1 \
        && cmake --build "$b" -j"$(nproc)" >"$b/build.log" 2>&1; then
        ok "tahoecursor compila contra os headers do KWin instalado"
    else
        bad "tahoecursor NÃO compila com o KWin $kwin_ver (o código precisa de ajuste, só recompilar não basta):"
        grep -E 'error' "$b/build.log" "$b/cmake.log" 2>/dev/null | head -5 >&2
    fi
fi

[[ $rc -eq 0 ]] && echo "kwin-check OK." || echo "kwin-check: há plugin para consertar." >&2
exit $rc
