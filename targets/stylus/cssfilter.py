"""CSS filter chain that turns a black element into a given color.

Port of the SPSA solver from the well-known "CSS filter generator" (Barrett Sonntag's
codepen, the same approach the Catppuccin lib used for @catppuccin-filters). The chain
starts from black, as in the lib's prefix `brightness(0) saturate(100%)`, then applies
invert, sepia, saturate, hue-rotate, brightness and contrast with the matrices from the
Filter Effects spec.

Deterministic: every random draw comes from a Random seeded with the target color and
the attempt number, and the iteration counts are fixed.
"""
import math
import random
import re

PREFIX = "brightness(0) saturate(100%)"
ATTEMPTS = 20         # independent wide+narrow solves per color; the best one wins
# Bump when the solver changes, so cached results (filters.json) are recomputed.
VERSION = f"spsa-1/{ATTEMPTS}"
# Highest loss the target accepts. With ATTEMPTS = 20 the palette tops out at ~2.2;
# 5 is the original generator's "close enough" mark (see docs/STYLUS-FILTERS.md).
LOSS_LIMIT = 5.0


def _clamp(v):
    return 0.0 if v < 0 else 255.0 if v > 255 else v


class _Color:
    __slots__ = ("r", "g", "b")

    def __init__(self, r=0.0, g=0.0, b=0.0):
        self.r, self.g, self.b = r, g, b

    def multiply(self, m):
        r, g, b = self.r, self.g, self.b
        self.r = _clamp(r * m[0] + g * m[1] + b * m[2])
        self.g = _clamp(r * m[3] + g * m[4] + b * m[5])
        self.b = _clamp(r * m[6] + g * m[7] + b * m[8])

    def hue_rotate(self, deg):
        a = deg / 180 * math.pi
        s, c = math.sin(a), math.cos(a)
        self.multiply((
            0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928,
            0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283,
            0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072,
        ))

    def sepia(self, v):
        w = 1 - v
        self.multiply((
            0.393 + 0.607 * w, 0.769 - 0.769 * w, 0.189 - 0.189 * w,
            0.349 - 0.349 * w, 0.686 + 0.314 * w, 0.168 - 0.168 * w,
            0.272 - 0.272 * w, 0.534 - 0.534 * w, 0.131 + 0.869 * w,
        ))

    def saturate(self, v):
        self.multiply((
            0.213 + 0.787 * v, 0.715 - 0.715 * v, 0.072 - 0.072 * v,
            0.213 - 0.213 * v, 0.715 + 0.285 * v, 0.072 - 0.072 * v,
            0.213 - 0.213 * v, 0.715 - 0.715 * v, 0.072 + 0.928 * v,
        ))

    def linear(self, slope, intercept=0.0):
        self.r = _clamp(self.r * slope + intercept * 255)
        self.g = _clamp(self.g * slope + intercept * 255)
        self.b = _clamp(self.b * slope + intercept * 255)

    def invert(self, v):
        self.r = _clamp((v + self.r / 255 * (1 - 2 * v)) * 255)
        self.g = _clamp((v + self.g / 255 * (1 - 2 * v)) * 255)
        self.b = _clamp((v + self.b / 255 * (1 - 2 * v)) * 255)

    def hsl(self):
        r, g, b = self.r / 255, self.g / 255, self.b / 255
        hi, lo = max(r, g, b), min(r, g, b)
        l = (hi + lo) / 2
        if hi == lo:
            return 0.0, 0.0, l * 100
        d = hi - lo
        s = d / (2 - hi - lo) if l > 0.5 else d / (hi + lo)
        if hi == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif hi == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        return h / 6 * 100, s * 100, l * 100


def _apply(values):
    c = _Color()
    c.invert(values[0] / 100)
    c.sepia(values[1] / 100)
    c.saturate(values[2] / 100)
    c.hue_rotate(values[3] * 3.6)
    c.linear(values[4] / 100)
    c.linear(values[5] / 100, -(0.5 * values[5] / 100) + 0.5)
    return c


class _Solver:
    def __init__(self, rgb, rng):
        self.target = rgb
        self.target_hsl = _Color(*rgb).hsl()
        self.rng = rng

    def loss(self, values):
        c = _apply(values)
        h, s, l = c.hsl()
        th, ts, tl = self.target_hsl
        tr, tg, tb = self.target
        return (abs(c.r - tr) + abs(c.g - tg) + abs(c.b - tb)
                + abs(h - th) + abs(s - ts) + abs(l - tl))

    @staticmethod
    def _fix(value, i):
        top = 7500 if i == 2 else 200 if i in (4, 5) else 100
        if i == 3:
            if value > top:
                value %= top
            elif value < 0:
                value = top + value % top
        elif value < 0:
            value = 0.0
        elif value > top:
            value = top
        return value

    def spsa(self, big_a, a, c, values, iters):
        gamma = 1 / 6
        best, best_loss = list(values), math.inf
        values = list(values)
        for k in range(iters):
            ck = c / (k + 1) ** gamma
            deltas = [1 if self.rng.random() > 0.5 else -1 for _ in range(6)]
            high = [v + ck * d for v, d in zip(values, deltas)]
            low = [v - ck * d for v, d in zip(values, deltas)]
            diff = self.loss(high) - self.loss(low)
            for i in range(6):
                g = diff / (2 * ck) * deltas[i]
                ak = a[i] / (big_a + k + 1)
                values[i] = self._fix(values[i] - ak * g, i)
            loss = self.loss(values)
            if loss < best_loss:
                best, best_loss = list(values), loss
        return best, best_loss

    def solve(self):
        best, best_loss = None, math.inf
        for _ in range(3):
            if best_loss <= 25:
                break
            values, loss = self.spsa(5, (60, 180, 18000, 600, 1.2, 1.2), 15,
                                     (50, 20, 3750, 50, 100, 100), 1000)
            if loss < best_loss:
                best, best_loss = values, loss
        a1 = best_loss + 1
        return self.spsa(best_loss, (0.25 * a1, 0.25 * a1, a1, 0.25 * a1, 0.2 * a1, 0.2 * a1),
                         2, best, 500)


def _rounded(values):
    return [round(values[0]), round(values[1]), round(values[2]), round(values[3] * 3.6) / 3.6,
            round(values[4]), round(values[5])]


def _css(values):
    inv, sep, sat, hue, bri, con = values
    return (f"{PREFIX} invert({inv}%) sepia({sep}%) saturate({sat}%) "
            f"hue-rotate({round(hue * 3.6)}deg) brightness({bri}%) contrast({con}%)")


def solve(hex_color, attempts=ATTEMPTS):
    """(css_filter, loss) for #RRGGBB. The loss is measured on the rounded values that
    actually end up in the CSS (0 = exact; under ~1 is indistinguishable)."""
    rgb = tuple(float(int(hex_color[i:i + 2], 16)) for i in (1, 3, 5))
    best = None
    for attempt in range(attempts):
        solver = _Solver(rgb, random.Random(f"{hex_color.upper()}/{attempt}"))
        values, _ = solver.solve()
        rounded = _rounded(values)
        loss = solver.loss(rounded)
        if best is None or loss < best[1]:
            best = (rounded, loss)
    values, loss = best
    shown = [int(v) if i != 3 else v for i, v in enumerate(values)]
    return _css(shown), loss


def render(css_filter):
    """RGB that a black pixel ends up as under `css_filter` (for tests and reports)."""
    m = re.findall(r"([a-z-]+)\(([-\d.]+)", css_filter)
    vals = dict(m)
    c = _apply([float(vals["invert"]), float(vals["sepia"]), float(vals["saturate"]),
                float(vals["hue-rotate"]) / 3.6, float(vals["brightness"]),
                float(vals["contrast"])])
    return c.r, c.g, c.b

