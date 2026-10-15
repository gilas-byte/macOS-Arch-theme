#!/usr/bin/env bash
# Deixa fonte e Plasma Style do tema visíveis para a tela de login (Plasma Login roda com
# um usuário próprio, que não lê a pasta pessoal). Precisa de root.
#   sudo targets/login/apply.sh install <id> <nome>   copia para pastas do sistema
#   sudo targets/login/apply.sh remove  <id>          apaga só o que o install criou
# Depois do install: Configurações do Sistema > Tela de login > "Aplicar configurações do Plasma".
set -euo pipefail
action=${1:?uso: apply.sh install <id> <nome> | remove <id>} id=${2:?id}
[[ $EUID -eq 0 ]] || { echo "precisa de root: sudo $0 $*" >&2; exit 1; }
user_home=$(getent passwd "${SUDO_USER:?rode com sudo, não como root direto}" | cut -d: -f6)
log=/var/lib/$id-theme/login-created
mkdir -p "$(dirname "$log")"

case $action in
install)
    name=${3:?nome}
    fonts=/usr/local/share/fonts/$id-apple
    style=/usr/share/plasma/desktoptheme/$name
    : > "$log"
    if [[ ! -e "$fonts" ]]; then
        install -d -m 755 "$fonts"
        find "$user_home/.local/share/fonts/$id-apple" -name 'SF-Pro-Text-*' -o -name 'SF-Pro-Display-*' \
            | while read -r f; do install -m 644 "$f" "$fonts/"; done
        echo "$fonts" >> "$log"
        fc-cache -f "$fonts" >/dev/null
    fi
    if [[ ! -e "$style" ]]; then
        cp -rL build/plasma-style/theme "$style"
        chmod -R a+rX "$style"
        echo "$style" >> "$log"
    fi
    echo "Copiado para o sistema:"; sed 's/^/  /' "$log"
    echo "Agora: Configurações do Sistema > Tela de login > \"Aplicar configurações do Plasma\"." ;;
remove)
    [[ -f "$log" ]] || { echo "nada criado pelo tema"; exit 0; }
    while read -r path; do
        case $path in
        /usr/local/share/fonts/$id-apple|/usr/share/plasma/desktoptheme/*) rm -rf "$path"; echo "  removido $path" ;;
        esac
    done < "$log"
    rm -f "$log"; rmdir --ignore-fail-on-non-empty "$(dirname "$log")"
    fc-cache -f >/dev/null ;;
esac
