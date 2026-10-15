#!/usr/bin/env python3
"""Gera templates/theme/ do alvo plasma-style (Plasma Style "Tahoe").

Parte do MacTahoe-Dark (vendor/MacTahoe-kde, GPL-3.0). Descompacta os .svgz para .svg
(o render só trabalha com texto, e o Plasma aceita os dois) e troca só a opacidade do
vidro por ${tokens} do palette.toml [surface]. O desenho é do MacTahoe.

Não edite templates/theme/ à mão: edite este arquivo.
"""
import gzip
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VENDOR = ROOT / "vendor/MacTahoe-kde/plasma/desktoptheme"
SRC = VENDOR / "MacTahoe-Dark"
OUT = HERE / "templates/theme"

# arquivo (sem extensão) -> [(trecho do MacTahoe, trecho com token)]
GLASS = {
    "dialogs/background": [("opacity:0.65;fill:#1a1a1a", "opacity:${surface_dialog_opacity};fill:#1a1a1a")],
    "widgets/tooltip": [("opacity:0.65;fill:#1a1a1a", "opacity:${surface_dialog_opacity};fill:#1a1a1a")],
    "widgets/panel-background": [("opacity:0.15;fill:#ffffff", "opacity:${surface_panel_veil};fill:#ffffff")],
}


def read_svg(path):
    data = path.read_bytes()
    if path.suffix == ".svgz":
        data = gzip.decompress(data)
    return data.decode("utf-8")


def svgs(root):
    for path in sorted(root.rglob("*")):
        if path.suffix in (".svg", ".svgz"):
            yield path


def build():
    files = {}
    # O install.sh do MacTahoe copia a pasta icons/ para dentro de cada tema.
    for base, prefix in ((SRC, ""), (VENDOR / "icons", "icons/")):
        for path in svgs(base):
            rel = prefix + str(path.relative_to(base).with_suffix(""))
            text = read_svg(path).replace("$", "$$")
            for old, new in GLASS.get(rel, []):
                if old not in text:
                    raise SystemExit(f"{rel}: trecho não encontrado: {old}")
                text = text.replace(old, new)
            files[rel + ".svg"] = text

    meta = json.loads((SRC / "metadata.json").read_text())
    plugin = meta["KPlugin"]
    plugin["Id"] = plugin["Name"] = "${theme_name}"
    plugin["Description"] = "${theme_name}: MacTahoe-Dark (Vince Liuice) com o vidro do palette.toml"
    for key in [k for k in plugin if k.startswith(("Name[", "Description["))]:
        del plugin[key]
    files["metadata.json"] = json.dumps(meta, indent=4, ensure_ascii=False) + "\n"
    files["plasmarc"] = (SRC / "plasmarc").read_text().replace("$", "$$")
    return files


def write(files):
    for rel, text in files.items():
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
    for path in sorted(OUT.rglob("*"), reverse=True):
        rel = str(path.relative_to(OUT))
        if path.is_file() and rel not in files:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()


write(build())
