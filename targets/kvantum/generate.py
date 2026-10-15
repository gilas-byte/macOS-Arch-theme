#!/usr/bin/env python3
"""Gera templates/theme.kvconfig e templates/theme.svg do alvo kvantum.

Parte do Kvantum MacTahoeDark (vendor/MacTahoe-kde) e troca só as cores: os hex do
MacTahoe viram ${tokens} da paleta, que o render resolve. O desenho dos widgets é o
do MacTahoe. Roda sozinho antes do render (chave "generate" do target.toml).

Não edite os templates à mão: edite os mapas abaixo.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "vendor/MacTahoe-kde/Kvantum/MacTahoe"

# [GeneralColors] do kvconfig: chave -> token.
GENERAL_COLORS = {
    "window.color": "bg_window",
    "inactive.window.color": "bg_window",
    "base.color": "bg_content",
    "inactive.base.color": "bg_content",
    "alt.base.color": "bg_alternate",
    "inactive.alt.base.color": "bg_alternate",
    "button.color": "bg_control",
    "highlight.color": "selection_bg",
    "inactive.highlight.color": "selection_bg_subtle",
    "text.color": "fg_primary",
    "inactive.text.color": "fg_primary",
    "window.text.color": "fg_primary",
    "inactive.window.text.color": "fg_secondary",
    "button.text.color": "fg_primary",
    "disabled.text.color": "fg_tertiary",
    "tooltip.base.color": "bg_elevated",
    "tooltip.text.color": "fg_primary",
    "highlight.text.color": "selection_fg",
    "inactive.highlight.text.color": "selection_fg",
    "link.color": "accent_primary",
    "link.visited.color": "sem_purple",
    "progress.indicator.text.color": "accent_on_primary",
}

# [%General] que muda em relação ao MacTahoe.
GENERAL = {
    # Barra de rolagem fina que aparece por cima do conteúdo, como no macOS.
    "transient_scrollbar": "true",
    # Vidro (palette.toml [surface]): o KWin borra o que fica atrás.
    "reduce_window_opacity": "${surface_window_glass_pct}",
    "reduce_menu_opacity": "${surface_menu_glass_pct}",
}

# Hex do SVG do MacTahoe -> token. O resto (pretos, brancos, cinzas de sombra) fica.
SVG_COLORS = {
    "#315bef": "accent_primary",
    "#3776e8": "accent_primary",
    "#597bf2": "accent_hover",
    "#195edc": "accent_pressed",
    "#195dda": "accent_pressed",
    "#242424": "bg_window",
}


def escape(text):
    return text.replace("$", "$$")


def kvconfig():
    text = escape((SRC / "MacTahoeDark.kvconfig").read_text())
    section = None
    out = []
    for line in text.splitlines():
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            section = m.group(1)
        key = line.split("=", 1)[0]
        if section == "GeneralColors" and key in GENERAL_COLORS:
            line = f"{key}=${{{GENERAL_COLORS[key]}}}"
        elif section == "%General" and key in GENERAL:
            line = f"{key}={GENERAL.pop(key)}"
        out.append(line)
    if GENERAL:
        raise SystemExit(f"chaves de [%General] não encontradas: {', '.join(GENERAL)}")
    return "\n".join(out) + "\n"


def svg():
    text = escape((SRC / "MacTahoeDark.svg").read_text())
    pattern = re.compile("|".join(SVG_COLORS), re.IGNORECASE)
    return pattern.sub(lambda m: f"${{{SVG_COLORS[m.group(0).lower()]}}}", text)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != content:
        path.write_text(content)


write(HERE / "templates/theme.kvconfig", kvconfig())
write(HERE / "templates/theme.svg", svg())
