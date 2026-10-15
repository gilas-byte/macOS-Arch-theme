import os
import re
import tomllib
from pathlib import Path

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
FN_RE = re.compile(r"^(lighten|darken|mix)\((.*)\)$")
RGBA_RE = re.compile(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)")
# Sombra no formato CSS: "x y blur rgba(...)" (px opcional).
SHADOW_RE = re.compile(r"^(-?\d+)(?:px)?\s+(-?\d+)(?:px)?\s+(\d+)(?:px)?\s+(rgba\(.*\))$")


class PaletteError(Exception):
    pass


def hex_to_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def _mix(a, b, t):
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex(x + (y - x) * t for x, y in zip(ra, rb))


def _resolve_ref(raw, ref):
    ref = ref.strip()
    if HEX_RE.match(ref):
        return ref
    section, _, key = ref.partition(".")
    try:
        value = raw[section][key]
    except KeyError:
        raise PaletteError(f"referência desconhecida: {ref}") from None
    if not (isinstance(value, str) and HEX_RE.match(value)):
        raise PaletteError(f"{ref} não é uma cor #RRGGBB")
    return value


def _compute(raw, expr):
    fn, args = FN_RE.match(expr).groups()
    parts = [p.strip() for p in args.split(",")]
    if fn in ("lighten", "darken") and len(parts) == 2:
        color, amount = _resolve_ref(raw, parts[0]), float(parts[1])
        return _mix(color, "#FFFFFF" if fn == "lighten" else "#000000", amount)
    if fn == "mix" and len(parts) == 3:
        return _mix(_resolve_ref(raw, parts[0]), _resolve_ref(raw, parts[1]), float(parts[2]))
    raise PaletteError(f"expressão inválida: {expr}")


def parse_rgba(value):
    """(r, g, b, alpha) de "rgba(...)", ou None."""
    m = RGBA_RE.fullmatch(value.strip())
    if not m:
        return None
    r, g, b, a = m.groups()
    return int(r), int(g), int(b), float(a)


def parse_shadow(value):
    """(x, y, blur, (r, g, b, alpha)) de "x y blur rgba(...)", ou None."""
    m = SHADOW_RE.match(value.strip())
    if not m or parse_rgba(m.group(4)) is None:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), parse_rgba(m.group(4))


def _rgba_variants(name, value):
    """SVG Tiny (QtSvg) não entende rgba(): cor e opacidade saem separadas.

    rgba(...)          -> ${x_hex}, ${x_alpha}, ${x_rgb}
    "x y blur rgba()"  -> o mesmo, mais ${x_x}, ${x_y}, ${x_blur}
    """
    out = {}
    shadow = parse_shadow(value)
    rgba = shadow[3] if shadow else parse_rgba(value)
    if rgba is None:
        return out
    r, g, b, a = rgba
    out[f"{name}_hex"] = rgb_to_hex((r, g, b))
    out[f"{name}_alpha"] = f"{a:g}"
    out[f"{name}_rgb"] = f"{r},{g},{b}"
    if shadow:
        out[f"{name}_x"], out[f"{name}_y"], out[f"{name}_blur"] = (str(v) for v in shadow[:3])
    return out


class Palette:
    def __init__(self, path):
        self.path = Path(path)
        with open(self.path, "rb") as f:
            self.raw = tomllib.load(f)
        # Perfil (profiles/<nome>.toml) por cima da paleta: só as chaves que ele define.
        self.profile = os.environ.get("THEME_PROFILE") or ""
        if self.profile:
            overlay = self.path.parent / "profiles" / f"{self.profile}.toml"
            if not overlay.is_file():
                raise PaletteError(f"perfil desconhecido: {self.profile} (veja profiles/)")
            with open(overlay, "rb") as f:
                for section, values in tomllib.load(f).items():
                    self.raw.setdefault(section, {}).update(values)
        for section in self.raw.values():
            for key, value in section.items():
                if isinstance(value, str) and FN_RE.match(value):
                    section[key] = _compute(self.raw, value)
        self.id = self.raw["theme"]["id"]
        self.name = self.raw["theme"]["name"]

    def color(self, dotted):
        return _resolve_ref(self.raw, dotted)

    def tokens(self):
        """Placeholders achatados para os templates."""
        out = {}
        for section, values in self.raw.items():
            for key, value in values.items():
                name = f"{section}_{key}"
                if isinstance(value, bool):
                    out[name] = "true" if value else "false"
                    continue
                out[name] = str(value)
                if isinstance(value, str) and HEX_RE.match(value):
                    r, g, b = hex_to_rgb(value)
                    out[f"{name}_nohash"] = value[1:]
                    out[f"{name}_rgb"] = f"{r},{g},{b}"
                    out[f"{name}_r"], out[f"{name}_g"], out[f"{name}_b"] = str(r), str(g), str(b)
                elif isinstance(value, float) and 0 <= value <= 1:
                    out[f"{name}_pct"] = str(round(value * 100))
                elif isinstance(value, str):
                    out.update(_rgba_variants(name, value))
        out["lnf_id"] = f"org.{self.id}.desktop"
        out["color_scheme"] = self.name
        return out
