#!/usr/bin/env python3
"""Build the stylus target from the Catppuccin userstyles.

Runs before the render ("generate" in target.toml). Pipeline:

  1. render the lib (lib.less.in -> templates/lib.less): a single flavor (the theme id), whose
     26 slots (+ `primary`) point at palette tokens.
  2. solve the CSS filter chain of each slot (cssfilter.py). Solving takes ~0.5 s per
     color, so results are memoized in filters.json (committed, keyed by hex and solver
     version); a color whose loss exceeds cssfilter.LOSS_LIMIT fails the generate.
  3. rewrite the ==UserStyle== header of every styles/*/catppuccin.user.less: our name and
     namespace, no @updateURL, single-option flavor selects, our accent list.
     Also fixes the upstream mixin calls that are missing their `[]` lookup (fix_upstream).
  4. embed the rendered lib in place of `@import ".../lib/std/v1.less"`: no hosting, no
     network, no style loading from a server that is not ours. The syntax-highlight CSS
     imports (@import url(...)) stay: they are plain CSS reading --ctp-*.
  5. alias the legacy flavors (latte, frappe, macchiato, mocha) to the theme flavor inside the lib,
     without touching the styles.
  6. report the hex literals of the upstream styles (build/stylus-report.md). They bypass
     the lib and stay pastel; the report only lists them, nothing is remapped.
  7. add the "Vidro Tahoe" style (glass.user.css.in) and assemble templates/import.json for Stylus (Manage -> Import), mirroring upstream's
     scripts/stylus-import/main.ts. It is big and derived from vendor/, so it is not
     committed (.gitignore); `$` is escaped as `$$` for the render.

Deterministic and only rewrites files whose content changed, like the other generators.
Do not edit templates/lib.less by hand: edit lib.less.in or this file and run
`python3 -m tooling render --only stylus`.
"""
import colorsys
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from tooling.palette import Palette  # noqa: E402
from tooling.render import render_text, write_if_changed  # noqa: E402

import cssfilter  # noqa: E402

PAL = Palette(ROOT / "palette.toml")
TEMPLATES = HERE / "templates"
REPORT = ROOT / "build/stylus-report.md"
UPSTREAM = ROOT / "vendor/catppuccin-userstyles"
FLAVOR = PAL.id
LEGACY_FLAVORS = ("latte", "frappe", "macchiato", "mocha")

# Lib slot -> palette token. Order = the upstream lib's order, plus `primary`
# (the macOS accent blue). mauve = systemPurple, lavender = systemIndigo clareado (web.lavender).
SLOTS = (
    ("rosewater", "web.rosewater"), ("flamingo", "web.flamingo"), ("pink", "sem.pink"),
    ("mauve", "sem.purple"), ("red", "sem.red"), ("maroon", "web.maroon"),
    ("peach", "sem.orange"), ("yellow", "sem.yellow"), ("green", "sem.green"),
    ("teal", "sem.teal"), ("sky", "web.sky"), ("sapphire", "web.sapphire"),
    ("blue", "sem.blue"), ("lavender", "web.lavender"), ("text", "fg.primary"),
    ("subtext1", "web.subtext1"), ("subtext0", "fg.secondary"), ("overlay2", "web.overlay2"),
    ("overlay1", "web.overlay1"), ("overlay0", "fg.tertiary"), ("surface2", "web.surface2"),
    ("surface1", "bg.control"), ("surface0", "bg.elevated"), ("base", "bg.content"),
    ("mantle", "web.mantle"), ("crust", "web.crust"), ("primary", "accent.primary"),
)


# Accent options: o azul do macOS é o padrão.
ACCENTS = (
    ("blue", "Azul*"), ("mauve", "Roxo"), ("pink", "Rosa"), ("red", "Vermelho"),
    ("peach", "Laranja"), ("yellow", "Amarelo"), ("green", "Verde"), ("teal", "Verde-água"),
    ("lavender", "Índigo"), ("subtext0", "Grafite"),
)

# Estilo extra com vidro (backdrop-filter) nas barras fixas de alguns sites.
GLASS = HERE / "glass.user.css.in"

LIB_IMPORT = '@import "https://userstyles.catppuccin.com/lib/std/v1.less";\n'
HEADER_RE = re.compile(r"\A/\* ==UserStyle==\n(.*?)\n==/UserStyle== \*/\n", re.S)


def placeholder(token):
    return "${" + token.replace(".", "_") + "}"


def flavor_map(name, kind, values):
    """`@<id>-<kind>: {...}` plus the `@<name>` map with our flavor and the legacy aliases."""
    body = " ".join(f"@{slot}: {value};" for slot, value in values)
    ruleset = f"@{FLAVOR}-{kind}"
    keys = "\n".join(f"  @{flavor}: {ruleset};" for flavor in (FLAVOR, *LEGACY_FLAVORS))
    return (f"/* deno-fmt-ignore */\n{ruleset}: {{ {body} }};\n\n"
            f"@{name}: {{\n{keys}\n}};")


def solve_filters():
    """Step 2: {slot: (filter, loss)}, memoized in filters.json."""
    path = HERE / "filters.json"
    cache = json.loads(path.read_text()) if path.is_file() else {}
    if cache.get("version") != cssfilter.VERSION:
        cache = {"version": cssfilter.VERSION, "colors": {}}
    known, used, out = cache["colors"], {}, {}
    for slot, token in SLOTS:
        color = PAL.color(token).upper()
        if color not in known:
            f, loss = cssfilter.solve(color)
            known[color] = {"filter": f, "loss": round(loss, 3)}
        used[color] = known[color]
        out[slot] = (known[color]["filter"], known[color]["loss"])
    cache["colors"] = dict(sorted(used.items()))
    write_if_changed(path, json.dumps(cache, indent=2) + "\n")
    bad = [f"{slot} ({loss})" for slot, (_, loss) in out.items() if loss > cssfilter.LOSS_LIMIT]
    if bad:
        sys.exit(f"stylus: filtro CSS acima do limite {cssfilter.LOSS_LIMIT}: {', '.join(bad)}")
    return out


def render_lib(filters):
    """Step 1: lib.less.in -> templates/lib.less, colors as ${tokens}."""
    lib = (HERE / "lib.less.in").read_text()
    lib = lib.replace("@@PALETTE@@",
                      flavor_map("catppuccin", "palette", ((s, placeholder(t)) for s, t in SLOTS)))
    lib = lib.replace("@@FILTERS@@",
                      flavor_map("catppuccin-filters", "filters", ((s, filters[s][0]) for s, _ in SLOTS)))
    write_if_changed(TEMPLATES / "lib.less", lib)
    return lib


def select(name, label, options):
    return f'@var select {name} "{label}" [' + ", ".join(f'"{v}:{l}"' for v, l in options) + "]"


def rewrite_header(site, source):
    """Step 3. Every rule must match exactly once, so an upstream format change fails
    loudly instead of shipping a half-rewritten header."""
    m = HEADER_RE.match(source)
    if not m:
        raise SystemExit(f"stylus: {site}: header ==UserStyle== não encontrado")
    flavor = [(FLAVOR, f"{PAL.name}*")]
    rules = (
        (r"^@name (.+) Catppuccin$", lambda m: f"@name {m[1]} {PAL.name}"),
        (r"^@namespace github\.com/catppuccin/userstyles/styles/(\S+)$",
         lambda m: f"@namespace github.com/tahoe-theme/{PAL.id}/styles/{m[1]}"),
        # Stylus checks @updateURL every 24 h and would overwrite the recolored style with
        # the original. Issues in our version are not Catppuccin's to triage.
        (r"^@updateURL .*\n", ""),
        (r"^@supportURL .*\n", ""),
        (r"^@description Soothing pastel theme for (.+)$",
         lambda m: f"@description Cores do macOS escuro ({PAL.name}) para {m[1]}"),
        (r"^@author Catppuccin$", f"@author {PAL.name} (baseado em Catppuccin Userstyles)"),
        (r"^@var select lightFlavor .*$", select("lightFlavor", "Light Flavor", flavor)),
        (r"^@var select darkFlavor .*$", select("darkFlavor", "Dark Flavor", flavor)),
        (r"^@var select accentColor .*$", select("accentColor", "Accent", ACCENTS)),
    )
    header = m[1]
    for pattern, repl in rules:
        header, n = re.subn(pattern, repl, header, flags=re.M)
        if n != 1:
            raise SystemExit(f"stylus: {site}: regra de header casou {n}x: {pattern}")
    return f"/* ==UserStyle==\n{header}\n==/UserStyle== */\n" + source[m.end():]


# Upstream bug: a few property values call the mixin without the `[]` lookup, e.g.
# `--bs-darkk-rgb: #lib.rgbify(@base);`. less 4.2 printed "[object Object]" there; the less
# bundled in Stylus rejects the whole style ("Rulesets cannot be evaluated on a property").
# Adding `[]` returns the mixin's last variable, which is what every other call does.
MIXIN_LOOKUP_RE = re.compile(r"(:\s*#lib\.(?:rgbify|hslify)\([^()]*\))(?=\s*[;}])")


def fix_upstream(source):
    """Mechanical fixes for upstream bugs that break compilation (see MIXIN_LOOKUP_RE)."""
    return MIXIN_LOOKUP_RE.sub(r"\1[]", source)


def embed_lib(site, source, lib):
    """Step 4. `lib` is the rendered lib (hex values, not ${tokens})."""
    if source.count(LIB_IMPORT) != 1:
        raise SystemExit(f"stylus: {site}: esperado 1 import da lib std/v1")
    embedded = f"/* {PAL.name} lib (palette.toml), embedded by generate.py */\n{lib.rstrip()}\n"
    return source.replace(LIB_IMPORT, embedded)


def upstream_styles():
    """[(site, source)] in site order."""
    root = UPSTREAM / "styles"
    if not root.is_dir():
        raise SystemExit("stylus: vendor/catppuccin-userstyles vazio; rode "
                         "`git submodule update --init`")
    return [(p.parent.name, p.read_text()) for p in sorted(root.glob("*/catppuccin.user.less"))]


HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
# Blanked before searching (newlines kept, so line numbers survive): comments and url(...).
SCRUB_RES = (
    re.compile(r"/\*.*?\*/", re.S),
    re.compile(r"(?<![:\"'\\])//[^\n]*"),
    re.compile(r"url\((?:[^()\"']|\"[^\"]*\"|'[^']*')*\)"),
)
OVERLAY0_TEXT_RE = re.compile(r"(?<![-\w])color:\s*@overlay0\b")


def _blank(m):
    return re.sub(r"[^\n]", " ", m.group(0))


def _neutral(hex_color):
    h = hex_color[1:]
    h = h[:6] if len(h) >= 6 else "".join(c * 2 for c in h[:3])
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    _, light, sat = colorsys.rgb_to_hls(r, g, b)
    return sat < 0.15 or light < 0.06 or light > 0.96


def hex_literals(source):
    """[(line, hex, context)] outside comments and url(). context: "valor" (a declaration
    value or a function/mixin argument), "string" (inside a quoted string, usually an inline SVG) or "seletor" (an
    attribute selector such as [fill="#fff"] or a Tailwind class such as .bg-\\[\\#fff\\],
    which matches the site's color and paints nothing). ID selectors (#add {) are skipped."""
    text = source
    for regex in SCRUB_RES:
        text = regex.sub(_blank, text)
    out = []
    for m in HEX_RE.finditer(text):
        start = m.start()
        line_start = text.rfind("\n", 0, start) + 1
        before = text[line_start:start]
        in_string = before.count('"') % 2 == 1 or before.count("'") % 2 == 1
        if in_string and re.search(r"\[[^\]]*$", before):
            context = "seletor"
        elif in_string:
            context = "string"
        else:
            nxt = re.search(r"[;{}]", text[m.end():])
            if not (nxt and nxt.group(0) == "{"):
                context = "valor"
            elif before.endswith("\\"):
                context = "seletor"     # escaped Tailwind class: .bg-\[\#E1F0F5\]
            else:
                continue                # ID selector
        out.append((text.count("\n", 0, start) + 1, m.group(0), context))
    return out


def write_report(styles):
    """Step 6: build/stylus-report.md. Only reports; remapping would silently break SVGs and
    gradients."""
    found = {site: hex_literals(src) for site, src in styles}
    found = {site: hits for site, hits in found.items() if hits}
    total = sum(len(h) for h in found.values())
    colored = sum(1 for hits in found.values() for _, x, _ in hits if not _neutral(x))
    overlay0 = {site: len(OVERLAY0_TEXT_RE.findall(src)) for site, src in styles}
    overlay0 = {site: n for site, n in overlay0.items() if n}
    uses = sum(len(re.findall(r"@overlay0\b", src)) for _, src in styles)

    lines = [
        "# Relatório do alvo stylus",
        "",
        f"Gerado por `targets/stylus/generate.py` a partir de `vendor/catppuccin-userstyles` "
        f"({(HERE / 'UPSTREAM').read_text().split()[1][:7]}). Não edite.",
        "",
        "## Hex literais",
        "",
        "Cores escritas à mão nos estilos: não passam pela lib, então não seguem a paleta e "
        "tendem a aparecer pastel no meio do marrom. Fora de comentários e `url()`. **Só "
        "relatório**: nada é remapeado. Contexto: `valor` = valor de "
        "propriedade ou argumento de função/mixin (pinta), `string` = dentro de string, quase "
        "sempre SVG inline (pinta), `seletor` = seletor de atributo tipo `[fill=\"#fff\"]` ou "
        "classe do Tailwind tipo `.bg-[#fff]` (só casa com a cor do site, não pinta).",
        "",
        f"**{total} hex em {len(found)} estilos**: {colored} coloridos, {total - colored} "
        "neutros (saturação < 15% ou quase preto/branco).",
        "",
        "| estilo | total | coloridos | valor | string | seletor |",
        "|---|---|---|---|---|---|",
    ]
    for site, hits in sorted(found.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        ctx = [sum(1 for *_, c in hits if c == k) for k in ("valor", "string", "seletor")]
        n_col = sum(1 for _, x, _ in hits if not _neutral(x))
        lines.append(f"| {site} | {len(hits)} | {n_col} | {ctx[0]} | {ctx[1]} | {ctx[2]} |")
    for title, want_neutral in (("Coloridos", False), ("Neutros", True)):
        lines += ["", f"### {title}", "", "| estilo | linha | hex | contexto |", "|---|---|---|---|"]
        for site, hits in sorted(found.items()):
            for line, x, ctx in hits:
                if _neutral(x) == want_neutral:
                    lines.append(f"| {site} | {line} | `{x}` | {ctx} |")
    lines += [
        "",
        "## `overlay0` como cor de texto",
        "",
        "`overlay0` = `fg.tertiary` (texto apagado, aviso conhecido como no KDE). "
        f"{uses} usos de `@overlay0` no total; destes, "
        f"{sum(overlay0.values())} são `color:` (texto) em {len(overlay0)} estilos. Se ficar "
        "fraco demais na prática, clarear só esse slot em `[web]`.",
        "",
        "| estilo | `color: @overlay0` |",
        "|---|---|",
    ]
    lines += [f"| {site} | {n} |" for site, n in sorted(overlay0.items())]
    REPORT.parent.mkdir(exist_ok=True)
    write_if_changed(REPORT, "\n".join(lines) + "\n")


# Recommended settings, as in upstream's import.json.
SETTINGS = {"settings": {"updateInterval": 24, "updateOnlyEnabled": True, "patchCsp": True,
                         "editor.linter": ""}}
VAR_RE = re.compile(r"""^(\S+)\s+(\S+)\s+(?:"([^"]*)"|'([^']*)')\s*(.*)$""")


def _loose_json(text):
    """Header arrays use single quotes at times: ['px']."""
    return json.loads(re.sub(r"'([^']*)'", lambda m: json.dumps(m[1]), text))


def parse_var(text):
    """One `@var` line (after "@var "), shaped like usercss-meta's output."""
    m = VAR_RE.match(text)
    if not m:
        raise SystemExit(f"stylus: @var não reconhecido: {text}")
    kind, name, label, value = m[1], m[2], m[3] if m[3] is not None else m[4], m[5].strip()
    var = {"type": kind, "label": label, "name": name, "value": None}
    if kind == "select":
        options, default = [], None
        for item in _loose_json(value):
            opt, _, opt_label = item.partition(":")
            opt_label = opt_label or opt
            if opt_label.endswith("*"):
                opt_label, default = opt_label[:-1], opt
            options.append({"name": opt, "label": opt_label, "value": opt})
        var["default"] = default if default is not None else options[0]["name"]
        var["options"] = options
    elif kind == "checkbox":
        var["default"], var["options"] = value, None
    elif kind == "range":
        default, lo, hi, step, *units = _loose_json(value)
        var.update(default=default, options=None, min=lo, max=hi, step=step,
                   units=units[0] if units else None)
    elif kind == "text":
        var["default"], var["options"] = value[1:-1] if value[:1] in "\"'" else value, None
    else:
        raise SystemExit(f"stylus: tipo de @var sem suporte: {kind}")
    return var


def parse_header(source):
    """usercssData: the ==UserStyle== keys in order, @var lines collected into `vars`."""
    meta = {}
    for line in HEADER_RE.match(source)[1].splitlines():
        if not line.startswith("@"):
            continue
        key, _, value = line[1:].partition(" ")
        if key == "var":
            var = parse_var(value)
            meta.setdefault("vars", {})[var["name"]] = var
        else:
            meta[key] = value.strip()
    return meta


def selected(styles):
    include = PAL.raw.get("stylus", {}).get("include", [])
    if not include:
        return styles
    unknown = sorted(set(include) - {site for site, _ in styles})
    if unknown:
        raise SystemExit(f"stylus: [stylus].include tem site(s) desconhecido(s): {', '.join(unknown)}")
    return [(site, src) for site, src in styles if site in include]


def write_import(styles):
    """Step 7. No updateUrl (Stylus would replace the style with the original);
    originalDigest is Stylus' calcStyleDigest for usercss: sha1 of the source."""
    entries = []
    for site, src in styles:
        meta = parse_header(src)
        entries.append({
            "enabled": True, "name": meta["name"], "description": meta["description"],
            "author": meta["author"], "usercssData": meta, "sourceCode": src,
            "originalDigest": hashlib.sha1(src.encode()).hexdigest(),
        })
    glass = render_text(GLASS.read_text(), PAL.tokens(), GLASS)
    meta = parse_header(glass)
    entries.append({
        "enabled": True, "name": meta["name"], "description": meta["description"],
        "author": meta["author"], "usercssData": meta, "sourceCode": glass,
        "originalDigest": hashlib.sha1(glass.encode()).hexdigest(),
    })
    entries.sort(key=lambda e: (e["name"].casefold(), e["name"]))
    text = json.dumps([SETTINGS, *entries], ensure_ascii=False, separators=(",", ":"))
    write_if_changed(TEMPLATES / "import.json", text.replace("$", "$$") + "\n")
    return len(entries)


def build_styles(lib_template=None):
    """Steps 3-5 for every style: [(site, source)]."""
    if lib_template is None:
        lib_template = (TEMPLATES / "lib.less").read_text()
    lib = render_text(lib_template, PAL.tokens(), TEMPLATES / "lib.less")
    out = []
    for site, src in upstream_styles():
        src = fix_upstream(rewrite_header(site, src))
        src = embed_lib(site, src, lib)
        out.append((site, src))
    return out


def main():
    lib = render_lib(solve_filters())
    write_import(selected(build_styles(lib)))
    write_report(upstream_styles())


if __name__ == "__main__":
    main()
