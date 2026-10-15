#!/usr/bin/env bash
# Uso: ./uninstall.sh [--only alvo[,alvo]] [--dry-run]
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

command -v python3 >/dev/null || { echo "erro: python3 não encontrado" >&2; exit 1; }

exec python3 -m tooling restore "$@"
