"""Time-of-day sky and the layered landscape behind the monument.

Rendered at screen resolution (smooth gradients, anti-aliased hills) only every
half minute; the animated scene is drawn on top of it.
"""

import math
import random

import cairo


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def mix(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


# hour, sky top, horizon, sun/moon, far hills, near hills, silhouette, stars
KEYS = [
    (0.0, "#060a17", "#18213d", "#e6ebff", "#18213b", "#10172b", "#05070d", 1.0),
    (4.8, "#0b1230", "#32365c", "#e6ebff", "#262c50", "#171d38", "#06080f", 0.7),
    (6.3, "#2b3c72", "#f2a88c", "#ffd9a8", "#6e5c88", "#3b3461", "#0d0c1a", 0.0),
    (8.0, "#3d72b8", "#cfe3ef", "#fff6e0", "#93abc8", "#5f7898", "#141a2a", 0.0),
    (13.0, "#2d6dc4", "#b8d8f0", "#ffffff", "#88a8cc", "#587ba4", "#141b2c", 0.0),
    (17.3, "#3a69ad", "#ead5b4", "#fff0c8", "#8e98b5", "#5e6b8f", "#141826", 0.0),
    (19.2, "#2a3470", "#f49c5f", "#ffd08a", "#8b5b7d", "#4d3b67", "#100c1a", 0.0),
    (20.4, "#151b42", "#6c4a79", "#ffd08a", "#3c3661", "#262547", "#08070f", 0.4),
    (21.8, "#060a17", "#18213d", "#e6ebff", "#18213b", "#10172b", "#05070d", 1.0),
    (24.0, "#060a17", "#18213d", "#e6ebff", "#18213b", "#10172b", "#05070d", 1.0),
]
FIXED_HOURS = {"dawn": 6.6, "day": 12.5, "sunset": 19.1, "night": 23.0}


def palette(hour):
    hour %= 24
    for a, b in zip(KEYS, KEYS[1:]):
        if a[0] <= hour <= b[0]:
            k = (hour - a[0]) / (b[0] - a[0])
            k = k * k * (3 - 2 * k)
            p = {}
            for i, name in enumerate(("top", "horizon", "sun", "far", "near", "sil"), start=1):
                p[name] = mix(hexc(a[i]), hexc(b[i]), k)
            p["stars"] = a[7] + (b[7] - a[7]) * k
            return p
    raise AssertionError(hour)


class Landscape:
    """Fixed terrain for one monitor; only the lighting changes with time."""

    def __init__(self, W, H, ground, seed):
        self.W, self.H, self.ground = W, H, ground
        rng = random.Random(seed)
        self.rng = rng
        g = ground

        def ridge(base, amp, freqs, step=4):
            ph = [rng.uniform(0, 6.3) for _ in freqs]
            pts = []
            for x in range(-step, W + 2 * step, step):
                y = base + sum(a * math.sin(x * f + p) for (f, a), p in zip(freqs, ph))
                pts.append((x, g - y * amp))
            return pts

        s = H / 720
        self.layers = [
            ridge(150 * s, 1.0, [(.004, 45 * s), (.011, 22 * s), (.027, 9 * s), (.06, 3 * s)]),
            ridge(80 * s, 1.0, [(.006, 25 * s), (.017, 12 * s), (.041, 4 * s)]),
            ridge(38 * s, 1.0, [(.005, 14 * s), (.013, 8 * s), (.05, 2 * s)]),
        ]
        self.stars = [(rng.uniform(0, W), rng.uniform(0, g * .6), rng.uniform(.4, 1.0), rng.random() < .12)
                      for _ in range(int(W * .12))]
        self.sun_x0 = rng.uniform(.1, .2)

    def sun_pos(self, hour, rise=6.0, set_=20.5):
        """The stylised arc used when the sky loops or is pinned."""
        g = self.ground
        if rise <= hour <= set_:
            k = (hour - rise) / (set_ - rise)
        else:
            k = ((hour - set_) % 24) / (24 - (set_ - rise))
        x = (self.sun_x0 + k * (1 - 2 * self.sun_x0)) * self.W
        y = g - math.sin(k * math.pi) * g * .78 + 10 * self.H / 720
        return x, y

    def project(self, alt, az, lat):
        """Sky position -> screen. We look towards the equator: east on the left
        in the northern hemisphere, the horizon just behind the hills."""
        facing = 180 if lat >= 0 else 0
        rel = ((az - facing + 540) % 360) - 180
        if lat < 0:
            rel = -rel
        horizon = self.ground - 14 * self.H / 720
        x = self.W * (.5 + rel / 250)
        y = horizon - alt / 70 * (horizon - 40 * self.H / 720)
        return x, y

    def render(self, out_w, out_h, state, t, picture=None):
        """state: from sky_state() - the hour the colours are keyed on, and where
        (if anywhere) the sun and moon are on screen."""
        p = palette(state["hour"])
        W, H, g = self.W, self.H, self.ground
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, out_w, out_h)
        cr = cairo.Context(surf)
        if picture and draw_picture(cr, picture, out_w, out_h):
            surf.flush()
            return surf, p
        cr.scale(out_w / W, out_h / H)
        s = H / 720

        grad = cairo.LinearGradient(0, 0, 0, g)
        grad.add_color_stop_rgb(0, *p["top"])
        grad.add_color_stop_rgb(.55, *mix(p["top"], p["horizon"], .45))
        grad.add_color_stop_rgb(1, *p["horizon"])
        cr.set_source(grad)
        cr.paint()

        if p["stars"] > 0.01:
            for x, y, b, big in self.stars:
                tw = .75 + .25 * math.sin(t * .3 + x)
                cr.set_source_rgba(1, 1, 1, p["stars"] * b * tw * (1 - y / (g * .7)))
                r = (1.1 if big else .6) * s
                cr.arc(x, y, r, 0, math.tau)
                cr.fill()

        if state.get("moon"):
            mx, my, lit, side = state["moon"]
            r = 14 * s
            day = 1 - p["stars"]
            glow = cairo.RadialGradient(mx, my, 0, mx, my, 110 * s)
            glow.add_color_stop_rgba(0, .9, .93, 1, .16 * lit * (1 - .8 * day))
            glow.add_color_stop_rgba(1, .9, .93, 1, 0)
            cr.set_source(glow)
            cr.paint()
            # the lit part: the bright limb faces the sun, the terminator is half an ellipse
            tx = side * (1 - 2 * lit)
            cr.move_to(mx, my - r)
            cr.arc(mx, my, r, -math.pi / 2, math.pi / 2) if side > 0 else cr.arc_negative(mx, my, r, -math.pi / 2, math.pi / 2)
            for i in range(21):
                a = math.pi / 2 - math.pi * i / 20
                cr.line_to(mx + tx * r * math.cos(a), my + r * math.sin(a))
            cr.close_path()
            cr.set_source_rgba(.93, .95, 1, .95 - .45 * day)
            cr.fill()
        if state.get("sun"):
            sx, sy = state["sun"]
            glow = cairo.RadialGradient(sx, sy, 0, sx, sy, 220 * s)
            glow.add_color_stop_rgba(0, *p["sun"], .55)
            glow.add_color_stop_rgba(1, *p["sun"], 0)
            cr.set_source(glow)
            cr.paint()
            cr.set_source_rgb(*p["sun"])
            cr.arc(sx, sy, 22 * s, 0, math.tau)
            cr.fill()

        def fill_ridge(pts, col):
            cr.move_to(pts[0][0], H)
            for x, y in pts:
                cr.line_to(x, y)
            cr.line_to(pts[-1][0], H)
            cr.close_path()
            cr.set_source_rgb(*col)
            cr.fill()

        def haze(strength, height):
            hz = cairo.LinearGradient(0, g - height, 0, g)
            hz.add_color_stop_rgba(0, *p["horizon"], 0)
            hz.add_color_stop_rgba(1, *p["horizon"], strength)
            cr.set_source(hz)
            cr.rectangle(0, g - height, W, height)
            cr.fill()

        fill_ridge(self.layers[0], p["far"])
        haze(.45, 160 * s)
        mid = mix(p["far"], p["near"], .5)
        fill_ridge(self.layers[1], mid)
        haze(.22, 90 * s)
        fill_ridge(self.layers[2], p["near"])
        surf.flush()
        return surf, p


def sky_state(t, config, landscape, loc, fixed_hour=None):
    """Colour hour plus on-screen sun and moon for moment t."""
    if config.sky == "clock" and loc and fixed_hour is None:
        from . import astro
        lat, lon = loc
        alt, az, rising = astro.sun(t, lat, lon)
        malt, maz, lit = astro.moon(t, lat, lon)
        hour = astro.equivalent_hour(alt, rising, astro.noon_altitude(t, lat))
        sx, sy = landscape.project(alt, az, lat)
        mx, my = landscape.project(malt, maz, lat)
        return {"hour": hour, "sun_alt": alt,
                "sun": (sx, sy) if alt > -3 else None,
                "moon": (mx, my, lit, 1 if sx > mx else -1) if malt > -3 and lit > .03 else None}
    if fixed_hour is not None:
        hour = fixed_hour
    elif config.sky in FIXED_HOURS:
        hour = FIXED_HOURS[config.sky]
    elif config.sky == "loop":
        hour = 24 * (t / config.sky_loop % 1)
    else:
        lt = __import__("time").localtime(t)
        hour = lt.tm_hour + lt.tm_min / 60
    h = hour % 24
    night = h > 20.5 or h < 6
    x, y = landscape.sun_pos(h)
    return {"hour": hour, "sun_alt": None,
            "sun": None if night else (x, y),
            "moon": (x, y, 1.0, 1) if night else None}


def draw_picture(cr, path, out_w, out_h):
    """Paint a user-chosen picture scaled to cover the screen; False if it can't be read."""
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        gi.require_version("Gdk", "4.0")
        gi.require_foreign("cairo")
        import warnings
        from gi.repository import Gdk, GdkPixbuf, GLib
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
    except (ImportError, ValueError, GLib.Error):
        return False
    k = max(out_w / pb.get_width(), out_h / pb.get_height())
    w, h = max(1, round(pb.get_width() * k)), max(1, round(pb.get_height() * k))
    pb = pb.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        Gdk.cairo_set_source_pixbuf(cr, pb, (out_w - w) / 2, (out_h - h) / 2)
    cr.paint()
    return True
