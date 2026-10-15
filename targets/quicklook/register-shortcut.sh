#!/usr/bin/env bash
# Registra o atalho do Quick Look no KWin agora (no Wayland o servidor de atalhos é o KWin e
# só lê o kglobalshortcutsrc ao iniciar). Componente terminado em .desktop = atalho que abre app.
# Uso: register-shortcut.sh <id> <nome> <atalho>
set -euo pipefail
id=$1 name=$2 keys=$3
code=$(python3 -c 'import sys; from PyQt6.QtGui import QKeySequence; print(QKeySequence(sys.argv[1])[0].toCombined())' "$keys" 2>/dev/null) || exit 0
action="['$id-quicklook.desktop', '_launch', 'Quick Look ($name)', 'Quick Look ($name)']"
kbuildsycoca6 >/dev/null 2>&1 || true
g() { gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel --method "org.kde.KGlobalAccel.$1" "${@:2}" >/dev/null; }
g doRegister "$action"
g setShortcutKeys "$action" "[([$code],)]" 6
