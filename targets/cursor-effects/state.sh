#!/usr/bin/env bash
# Compila e instala o efeito tahoecursor. Roda como usuário; só o install usa sudo.
# Num terminal, pede a senha do sudo; sem terminal, só mostra o comando a rodar.
# Uso: state.sh get|set|stamp <id>   |   state.sh restore <id> <valor-antigo>
# O carimbo junta o código e a versão do KWin: o KWin só carrega plugin compilado para a
# versão exata dele, então um update do KWin também pede recompilação.
set -euo pipefail
src=effects/tahoecursor
so=${TAHOE_CURSOR_SO:-/usr/lib/qt6/plugins/kwin/effects/plugins/tahoecursor.so}
build=build/_cmake-tahoecursor
stamp="${XDG_STATE_HOME:-$HOME/.local/state}/$2/tahoecursor.sha256"

kwin_version() { echo "${KWIN_VERSION:-$(kwin_wayland --version 2>/dev/null | cut -d' ' -f2)}"; }
stamp_value() {
    { find "$src" -type f -print0 | sort -z | xargs -0 sha256sum; echo "kwin $(kwin_version)"; } | sha256sum | cut -d' ' -f1
}

case "$1" in
get)
    if [[ ! -f $so ]]; then echo ausente
    elif [[ -f $stamp && $(cat "$stamp") == "$(stamp_value)" ]]; then echo atualizado
    else echo desatualizado; fi
    ;;
set)
    cmake -S "$src" -B "$build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr >/dev/null
    cmake --build "$build" -j"$(nproc)" >/dev/null
    if [[ -t 0 ]]; then
        sudo cmake --install "$build" >/dev/null
        mkdir -p "$(dirname "$stamp")"
        stamp_value >"$stamp"
        qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect tahoecursor >/dev/null || true
        echo "  tahoecursor instalado. Se ele já estava ligado, faça logout/login pra versão nova entrar."
    else
        echo "  tahoecursor precisa de sudo. Rode num terminal, na raiz do repo:"
        echo "    sudo cmake --install $build && ./install.sh --only cursor-effects"
    fi
    ;;
stamp) stamp_value ;;
restore)
    # só dá pra desfazer a instalação; uma versão antiga do plugin não fica guardada
    [[ ${3:-} == ausente && -f $so ]] || exit 0
    qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect tahoecursor >/dev/null || true
    if [[ -t 0 ]]; then
        sudo rm -f "$so"
        rm -f "$stamp"
    else
        echo "  Remova o plugin num terminal: sudo rm $so"
    fi
    ;;
*) echo "uso: $0 get|set|stamp|restore <id> [valor]" >&2; exit 1 ;;
esac
