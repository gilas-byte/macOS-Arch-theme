#!/usr/bin/env bash
# Compila e instala o efeito tahoecursor. Roda como usuário; só o install usa sudo.
# Num terminal, pede a senha do sudo; sem terminal, só mostra o comando a rodar.
# Uso: state.sh get|set <id>   |   state.sh restore <id> <valor-antigo>
set -euo pipefail
src=effects/tahoecursor
so=/usr/lib/qt6/plugins/kwin/effects/plugins/tahoecursor.so
build=build/_cmake-tahoecursor
stamp="${XDG_STATE_HOME:-$HOME/.local/state}/$2/tahoecursor.sha256"

src_hash() { find "$src" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1; }

case "$1" in
get)
    if [[ ! -f $so ]]; then echo ausente
    elif [[ -f $stamp && $(cat "$stamp") == "$(src_hash)" ]]; then echo atualizado
    else echo desatualizado; fi
    ;;
set)
    cmake -S "$src" -B "$build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr >/dev/null
    cmake --build "$build" -j"$(nproc)" >/dev/null
    if [[ -t 0 ]]; then
        sudo cmake --install "$build" >/dev/null
        mkdir -p "$(dirname "$stamp")"
        src_hash >"$stamp"
        qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect tahoecursor >/dev/null || true
        echo "  tahoecursor instalado. Se ele já estava ligado, faça logout/login pra versão nova entrar."
    else
        echo "  tahoecursor precisa de sudo. Rode num terminal, na raiz do repo:"
        echo "    sudo cmake --install $build && ./install.sh --only cursor-effects"
    fi
    ;;
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
*) echo "uso: $0 get|set|restore <id> [valor]" >&2; exit 1 ;;
esac
