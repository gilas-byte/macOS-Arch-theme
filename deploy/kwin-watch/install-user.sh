#!/usr/bin/env bash
# Instala o vigia de update do KWin como unidades de USUÁRIO (sem sudo). Desfazer: ./install-user.sh --remove
set -euo pipefail
d="$(dirname "$(readlink -f "$0")")"; u="$HOME/.config/systemd/user"
if [[ ${1:-} == --remove ]]; then
    systemctl --user disable --now tahoe-kwin-watch.path 2>/dev/null || true
    rm -f "$u/tahoe-kwin-watch.path" "$u/tahoe-kwin-watch.service"; systemctl --user daemon-reload; echo removido; exit 0
fi
mkdir -p "$u"; cp "$d/tahoe-kwin-watch.path" "$d/tahoe-kwin-watch.service" "$u/"
systemctl --user daemon-reload; systemctl --user enable --now tahoe-kwin-watch.path
systemctl --user is-active tahoe-kwin-watch.path
