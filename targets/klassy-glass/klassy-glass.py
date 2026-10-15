#!/usr/bin/env python3
"""Barra de título de vidro (Klassy) só em algumas janelas.

O Klassy aplica um preset inteiro às janelas de uma exceção. O preset "<Nome> Vidro" é uma
cópia da config atual do Klassy (klassyrc) com a barra translúcida e borrada; a exceção
"Windeco Exception N" liga esse preset às classes de janela do palette.toml.

  get <nome>                         imprime a opacidade da barra no preset (vazio se não há exceção)
  set <nome> <classes> <opacidade>   (re)cria preset e exceção
  restore <nome> <classes> <valor>   valor vazio: apaga preset e exceção
"""
import os
import re
import subprocess
import sys
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "klassy"
KLASSYRC = CONFIG / "klassyrc"
PRESETS = CONFIG / "windecopresetsrc"
GROUP_RE = re.compile(r"^\[(.+)\]\s*$")
# Grupos do klassyrc que não são da decoração (o próprio Klassy pula estes ao salvar preset).
SKIP = re.compile(r"^(Global|Style|SystemIconGeneration|Windeco Exception \d+|Default Windeco Exception \d+)$")


def parse(path):
    """[(grupo, [(chave, valor)])] na ordem do arquivo."""
    groups = []
    if not path.exists():
        return groups
    for line in path.read_text().splitlines():
        m = GROUP_RE.match(line)
        if m:
            groups.append((m[1], []))
        elif "=" in line and groups:
            key, _, value = line.partition("=")
            groups[-1][1].append((key.strip(), value))
    return groups


def dump(groups):
    return "".join(f"[{g}]\n" + "".join(f"{k}={v}\n" for k, v in items) + "\n" for g, items in groups)


def names(theme):
    return f"{theme} Vidro", f"Windeco Preset {theme} Vidro"


def ours(groups, preset):
    return [g for g, items in groups if g.startswith("Windeco Exception ")
            and dict(items).get("ExceptionPreset") == preset]


def reload():
    for cmd in (["dbus-send", "--session", "--type=signal", "/KlassyDecoration",
                 "org.kde.Klassy.Style.updateDecorationColorCache"],
                ["dbus-send", "--session", "--type=signal", "/KWin", "org.kde.KWin.reloadConfig"]):
        subprocess.run(cmd, check=False)


def remove(theme):
    preset, preset_group = names(theme)
    rc = parse(KLASSYRC)
    drop = set(ours(rc, preset))
    kept = [(g, i) for g, i in rc if g not in drop]
    # As exceções são lidas em sequência (0, 1, 2...): renumera as que sobraram.
    n = 0
    for idx, (g, items) in enumerate(kept):
        if g.startswith("Windeco Exception "):
            kept[idx] = (f"Windeco Exception {n}", items)
            n += 1
    if drop:
        KLASSYRC.write_text(dump(kept))
    presets = parse(PRESETS)
    if any(g == preset_group for g, _ in presets):
        PRESETS.write_text(dump([(g, i) for g, i in presets if g != preset_group]))


def apply(theme, classes, opacity):
    remove(theme)
    preset, preset_group = names(theme)
    flat = {}
    for g, items in parse(KLASSYRC):
        if not SKIP.match(g):
            flat.update(items)
    flat.update({
        "ActiveTitleBarOpacity": opacity, "InactiveTitleBarOpacity": opacity,
        "BlurTransparentTitleBars": "true", "OpaqueMaximizedTitleBars": "false",
        "DrawTitleBarSeparator": "false",
    })
    CONFIG.mkdir(parents=True, exist_ok=True)
    presets = parse(PRESETS) + [(preset_group, sorted(flat.items()))]
    PRESETS.write_text(dump(presets))

    rc = parse(KLASSYRC)
    n = sum(1 for g, _ in rc if g.startswith("Windeco Exception "))
    rc.append((f"Windeco Exception {n}", [
        ("Enabled", "true"), ("ExceptionPreset", preset),
        ("ExceptionProgramNamePattern", ""), ("ExceptionWindowPropertyPattern", classes),
        ("ExceptionWindowPropertyType", "ExceptionWindowClassName"),
    ]))
    KLASSYRC.write_text(dump(rc))


def main():
    action, theme = sys.argv[1], sys.argv[2]
    preset, _ = names(theme)
    if action == "get":
        if ours(parse(KLASSYRC), preset):
            _, group = names(theme)
            items = dict(next((i for g, i in parse(PRESETS) if g == group), []))
            print(items.get("ActiveTitleBarOpacity", ""))
        return
    classes, value = sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ""
    if action == "set" and value:
        apply(theme, classes, value)
    else:
        remove(theme)
    reload()


main()
