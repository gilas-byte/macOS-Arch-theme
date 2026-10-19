#!/usr/bin/env bash
# Compila e instala o efeito tahoecursor na pasta do USUÁRIO (sem sudo).
# O KWin acha o plugin por QT_PLUGIN_PATH, definido em ~/.config/plasma-workspace/env/tahoe-plugins.sh
# (arquivo do alvo, lido no início da sessão do Plasma: precisa de logout/login).
# Uso: state.sh get|set <id>   |   state.sh restore <id> <valor-antigo>
set -euo pipefail
src=effects/tahoecursor
prefix="$HOME/.local"
so="$prefix/lib/qt6/plugins/kwin/effects/plugins/tahoecursor.so"
build=build/_cmake-tahoecursor
stamp="${XDG_STATE_HOME:-$HOME/.local/state}/$2/tahoecursor.sha256"

src_hash() { find "$src" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1; }
kwin_ver() { pacman -Q kwin 2>/dev/null | awk '{print $2}' | sed -E 's/^[0-9]+://; s/-[0-9.]+$//'; }
built_ver() { grep -a -o 'org\.kde\.kwin\.EffectPluginFactory[0-9][0-9.]*' "$so" | head -1 | sed 's/.*Factory//'; }

case "$1" in
get)
    # atualizado = código igual ao instalado E compilado para o KWin que está instalado agora
    if [[ ! -f $so ]]; then echo ausente
    elif [[ -f $stamp && $(cat "$stamp") == "$(src_hash)" && $(built_ver) == "$(kwin_ver)" ]]; then echo atualizado
    else echo desatualizado; fi
    ;;
set)
    cmake -S "$src" -B "$build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
        -DKDE_INSTALL_QTPLUGINDIR=lib/qt6/plugins >/dev/null
    cmake --build "$build" -j"$(nproc)" >/dev/null
    # instala numa pasta temporária e troca por rename: sobrescrever o .so no lugar corromperia o
    # plugin velho que o KWin em execução ainda tem mapeado na memória
    stage=$(mktemp -d "${TMPDIR:-/tmp}/tahoecursor-stage.XXXXXX")
    cmake --install "$build" --prefix "$stage" >/dev/null
    mkdir -p "$(dirname "$so")"
    cp "$stage/lib/qt6/plugins/kwin/effects/plugins/tahoecursor.so" "$so.new"
    mv -f "$so.new" "$so"
    rm -rf "$stage"
    mkdir -p "$(dirname "$stamp")"
    src_hash >"$stamp"
    echo "  tahoecursor instalado em $so (sem sudo). Faça logout/login pra versão nova entrar."
    ;;
restore)
    # só dá pra desfazer a instalação; uma versão antiga do plugin não fica guardada
    [[ ${3:-} == ausente && -f $so ]] || exit 0
    qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect tahoecursor >/dev/null || true
    rm -f "$so" "$stamp"
    ;;
*) echo "uso: $0 get|set|restore <id> [valor]" >&2; exit 1 ;;
esac
