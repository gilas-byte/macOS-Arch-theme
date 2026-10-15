#!/usr/bin/env python3
"""Checks for the stylus target. Does not touch the system.

- templates/lib.less and filters.json are up to date and generate.py is deterministic;
- filters.json matches a fresh solve and every loss is under the limit;
- the generated lib has every name of the upstream lib (superset);
- no #RRGGBB in the target's own sources (lib.less.in, templates/lib.less);
- import.json: valid, no @updateURL/updateUrl, single-option flavor selects, digests,
  no leftover placeholder;
- contrast of the text-like slots over base (known warnings: red, maroon, overlay0);
- optional: compiles every style with less.js if node and less are available.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "targets/stylus"
BUILD = ROOT / "build/stylus"
sys.path[:0] = [str(ROOT), str(TARGET)]

import cssfilter  # noqa: E402
import generate  # noqa: E402
from tooling.contrast import ratio  # noqa: E402

failures = []

AA, FAINT = 4.5, 3.0
# slot -> minimum. Chromatic slots and text-like neutrals; surfaces are backgrounds.
CONTRAST = {slot: AA for slot in (
    "rosewater", "flamingo", "pink", "mauve", "red", "maroon", "peach", "yellow", "green",
    "teal", "sky", "sapphire", "blue", "lavender", "text", "subtext1", "subtext0", "overlay2",
    "primary")}
CONTRAST["overlay1"] = FAINT     # web.overlay1, "faint" text
CONTRAST["overlay0"] = FAINT     # fg.tertiary, disabled text
# Avisos conhecidos: avisos aceitos ficam aqui.
KNOWN = set()


def check(ok, message):
    print(("PASSOU: " if ok else "FALHOU: ") + message)
    if not ok:
        failures.append(message)


def warn(message):
    print("AVISO:  " + message)


def digest():
    files = [TARGET / "templates/lib.less", TARGET / "filters.json"]
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


# --- generator ---------------------------------------------------------------------------
before = digest()
subprocess.run([sys.executable, TARGET / "generate.py"], check=True)
after = digest()
check(after == before, "lib.less e filters.json em dia com generate.py e a paleta (rode o render e commite)")
subprocess.run([sys.executable, TARGET / "generate.py"], check=True)
check(digest() == after, "generate.py determinístico")

cache = json.loads((TARGET / "filters.json").read_text())
stale = []
for color, entry in cache["colors"].items():
    f, loss = cssfilter.solve(color)
    if (f, round(loss, 3)) != (entry["filter"], entry["loss"]):
        stale.append(color)
check(not stale, f"filters.json igual a um solve do zero {stale[:3] if stale else ''}")
worst = max(cache["colors"].items(), key=lambda kv: kv[1]["loss"])
check(worst[1]["loss"] <= cssfilter.LOSS_LIMIT,
      f"perda dos filtros <= {cssfilter.LOSS_LIMIT} (pior: {worst[0]} {worst[1]['loss']})")

# --- lib ---------------------------------------------------------------------------------
upstream_lib = (generate.UPSTREAM / "lib/std/v1.less").read_text()
our_lib = (TARGET / "templates/lib.less").read_text()


def names(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return (set(re.findall(r"@[\w-]+", text)) | set(re.findall(r"\.[\w-]+\(\)", text))
            | set(re.findall(r"--ctp-[\w-]+", text)) | set(re.findall(r"#[a-z][\w-]*(?= \{)", text)))


missing = sorted(names(upstream_lib) - names(our_lib))
check(not missing, f"lib gerada tem todos os nomes da lib original {missing[:5] if missing else ''}")

hexes = [(p.name, m) for p in (TARGET / "lib.less.in", TARGET / "templates/lib.less")
         for m in re.findall(r"#[0-9A-Fa-f]{6}\b", p.read_text())]
check(not hexes, f"nenhum hex solto nas fontes do alvo {hexes[:3] if hexes else ''}")

# --- import.json -------------------------------------------------------------------------
subprocess.run([sys.executable, "-m", "tooling", "render", "--only", "stylus"], cwd=ROOT,
               check=True, stdout=subprocess.DEVNULL)
data = json.loads((BUILD / "import.json").read_text())
# O "Vidro <tema>" é um estilo próprio (glass.user.css.in), checado à parte.
glass = [s for s in data[1:] if s["name"] == f"Vidro {generate.PAL.name}"]
styles = [s for s in data[1:] if s not in glass]
check(len(glass) == 1 and "backdrop-filter" in glass[0]["sourceCode"] and "${" not in glass[0]["sourceCode"],
      "estilo de vidro presente e renderizado")
include = generate.PAL.raw.get("stylus", {}).get("include", [])
expected = len(include) or len(generate.upstream_styles())
check("settings" in data[0] and len(styles) == expected, f"import.json com {len(styles)} estilos (esperado {expected})")
check(not any("${" in s["sourceCode"] for s in styles), "nenhum placeholder sobrando")
check(not any("@updateURL" in s["sourceCode"] or "updateUrl" in s or "updateURL" in s["usercssData"]
              for s in styles), "nenhum @updateURL / updateUrl")
check(not any("userstyles.catppuccin.com/lib" in s["sourceCode"] for s in styles), "lib embutida (sem import remoto)")
unfixed = [s["name"] for s in styles if generate.MIXIN_LOOKUP_RE.search(s["sourceCode"])]
check(not unfixed, f"chamadas #lib.rgbify/hslify com [] (bug do upstream corrigido) {unfixed[:3] if unfixed else ''}")
flavors = [(s["name"], v) for s in styles for v in ("lightFlavor", "darkFlavor")
           if [o["name"] for o in s["usercssData"]["vars"][v]["options"]] != [generate.FLAVOR]]
check(not flavors, f"selects de flavor com uma opção só ({generate.FLAVOR}) {flavors[:3] if flavors else ''}")
accents = {tuple(o["name"] for o in s["usercssData"]["vars"]["accentColor"]["options"]) for s in styles}
ours = tuple(a for a, _ in generate.ACCENTS)
check(accents == {ours}, "acentos de generate.ACCENTS em todos os estilos")
check(all(hashlib.sha1(s["sourceCode"].encode()).hexdigest() == s["originalDigest"] for s in styles),
      "originalDigest = sha1(sourceCode)")
names_sorted = [s["name"] for s in styles]
check(names_sorted == sorted(names_sorted, key=lambda n: (n.casefold(), n)), "ordem alfabética")

# --- contrast ----------------------------------------------------------------------------
bg = generate.PAL.color("bg.content")
tokens = dict(generate.SLOTS)
for slot, minimum in CONTRAST.items():
    r = ratio(generate.PAL.color(tokens[slot]), bg)
    if r >= minimum:
        continue
    if slot in KNOWN:
        warn(f"{slot} ({tokens[slot]}) {r:.2f}:1 sobre bg.content (conhecido, mín {minimum})")
    else:
        check(False, f"contraste de {slot} ({tokens[slot]}) {r:.2f}:1 < {minimum}")
check(True, "contraste dos slots de texto sobre bg.content (fora os avisos conhecidos)")
report = ROOT / "build/stylus-report.md"
check(report.is_file() and "`color: @overlay0`" in report.read_text(),
      "build/stylus-report.md com hex literais e usos de overlay0 como texto")

# --- optional: less.js -------------------------------------------------------------------
node = shutil.which("node")
probe = node and subprocess.run([node, "-e", f"require({json.dumps(os.environ.get('LESS_MODULE', 'less'))})"],
                                capture_output=True).returncode == 0
if not probe:
    warn("node/less não encontrados: pulando a compilação dos estilos "
         "(npm install less e rode com LESS_MODULE=<caminho>/node_modules/less)")
else:
    result = subprocess.run([node, ROOT / "tests/stylus-compile.js", BUILD / "import.json"],
                            capture_output=True, text=True)
    print(result.stdout.rstrip())
    check(result.returncode == 0, "todos os estilos compilam com less.js")

print("\nStylus OK." if not failures else f"\n{len(failures)} falha(s).")
sys.exit(1 if failures else 0)
