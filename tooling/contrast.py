from .palette import _mix, hex_to_rgb

AA = 4.5
FAINT = 3.0

# (texto, fundo, mínimo). Pares obrigatórios: texto legível nos fundos principais.
REQUIRED = [
    ("fg.primary", "bg.window", AA),
    ("fg.primary", "bg.content", AA),
    ("fg.primary", "bg.header", AA),
    ("fg.secondary", "bg.window", AA),
    ("accent.on_primary", "accent.primary", FAINT),
    ("selection.fg", "selection.bg", AA),
]

# Pares informativos: só avisam. fg.tertiary é texto desabilitado (isento no WCAG).
ADVISORY = [
    ("fg.primary", "bg.elevated", AA),
    ("fg.primary", "bg.control", AA),
    ("fg.secondary", "bg.content", AA),
    ("fg.tertiary", "bg.window", FAINT),
    ("selection.fg", "selection.bg_subtle", AA),
]


def _luminance(hex_color):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in hex_to_rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg):
    a, b = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


# Vidro: o pior caso do texto é o popup do Plasma (#1a1a1a do MacTahoe a dialog_opacity)
# sobre um fundo todo branco. (texto, opacidade do vidro, mínimo)
GLASS_TINT = "#1A1A1A"
GLASS = [("fg.primary", "surface.dialog_opacity", AA), ("fg.secondary", "surface.dialog_opacity", FAINT)]


def check(palette, out=print):
    failed = False
    for pairs, required in ((REQUIRED, True), (ADVISORY, False)):
        out("Pares obrigatórios:" if required else "Pares informativos:")
        for fg, bg, minimum in pairs:
            r = ratio(palette.color(fg), palette.color(bg))
            ok = r >= minimum
            tag = "ok" if ok else ("FALHA" if required else "aviso")
            out(f"  {tag:<5} {fg:>18} sobre {bg:<14} {r:5.2f}:1 (mín {minimum})")
            failed |= required and not ok
    out("Vidro (pior caso: fundo branco atrás do popup):")
    for fg, key, minimum in GLASS:
        section, _, name = key.partition(".")
        bg = _mix("#FFFFFF", GLASS_TINT, palette.raw[section][name])
        r = ratio(palette.color(fg), bg)
        ok = r >= minimum
        out(f"  {'ok' if ok else 'FALHA':<5} {fg:>18} sobre vidro {bg}  {r:5.2f}:1 (mín {minimum})")
        failed |= not ok
    return not failed
