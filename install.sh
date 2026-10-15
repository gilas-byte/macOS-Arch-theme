#!/usr/bin/env bash
# Uso: ./install.sh [--only alvo[,alvo]] [--dry-run] [--list]
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

die() { echo "erro: $*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 não encontrado (sudo pacman -S python)"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || die "precisa de Python >= 3.11"
for cmd in kreadconfig6 kwriteconfig6 pacman; do
    command -v "$cmd" >/dev/null || die "$cmd não encontrado (este tema é para Arch + KDE Plasma 6)"
done

exec python3 -m tooling apply "$@"
