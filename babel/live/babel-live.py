#!/usr/bin/env python3
"""Babel - a live pixel-art wallpaper for Omarchy.

Tiny silhouette workers build a monument brick by brick, a random disaster
flattens it, and the survivors walk back in and start the next one. Forever.

  babel-live.py                  live on every monitor (layer behind windows)
  babel-live.py --window         in a normal window, for development
  babel-live.py --snapshot OUT   render one frame to a PNG and exit

  --speed N          run the simulation N times faster (preview a whole cycle)
  --monument NAME    start with this monument
  --disaster NAME    (snapshot) jump straight to this disaster
  --progress P       (snapshot) build progress 0..1
  --at SECONDS       (snapshot) simulate this long before rendering
"""

import argparse
import math
import os
import random
import sys
import time

import cairo

FPS = 12
ART_H = 270  # target art-pixel rows; the real value is picked per monitor
GRAVITY = 170.0
BW, BH = 4, 3  # brick size in art pixels
WORKERS = 14

BUILD_TIME = 200.0
ADMIRE_TIME = 45.0
RECOVER_TIME = 25.0


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


SKY = [rgb(c) for c in (
    "#141124", "#1c1630", "#28193a", "#3a1f45", "#55264d", "#763052",
    "#9a3d52", "#c0524f", "#df7350", "#f09a58")]
SIL = rgb("#0c0910")
HILL_FAR = rgb("#5a2c4c")
HILL_NEAR = rgb("#3b2240")
SUN_HI = rgb("#fbe2a2")
SUN_LO = rgb("#f6b46a")
STAR = rgb("#efe3cf")
WATER = rgb("#111a2e")
WATER_HI = rgb("#2a4466")
FOAM = rgb("#e4edf2")
FIRE1, FIRE2, FIRE3 = rgb("#fff4c4"), rgb("#ffb347"), rgb("#e2532c")
BREATH, BREATH_CORE = rgb("#6fd8ff"), rgb("#f0fcff")
BEAM = rgb("#a6f7dc")
EYE = rgb("#ff4a2e")
FUNNEL, FUNNEL_HI = rgb("#221b2c"), rgb("#43384f")
SMOKE = rgb("#4a3d52")
UFO_LIGHT = rgb("#ffe066")


# --------------------------------------------------------------------------
# Monuments: each is a function (x, yb) -> filled?, with yb counted up from
# the ground. Shapes are designed for ART_H ~ 270.

def pyramid():
    w, h, c = 181, 96, 90
    return w, h, lambda x, yb: abs(x - c) <= 90 - 6 * (yb // 6)


def parthenon():
    w, h, c = 171, 80, 85
    cols = [c - 66 + i * 132 / 7 for i in range(8)]

    def f(x, yb):
        dx = abs(x - c)
        if yb < 3:
            return dx <= 85
        if yb < 6:
            return dx <= 81
        if yb < 9:
            return dx <= 77
        if yb < 52:
            hw = 4 if yb < 10 or yb > 48 else 3
            return any(abs(x - cc) <= hw for cc in cols)
        if yb < 62:
            return dx <= 74
        if yb < 64:
            return dx <= 77
        return dx <= 76 * (1 - (yb - 64) / 16)
    return w, h, f


def skyscraper():
    w, h, c = 73, 200, 36
    tiers = [(0, 98, 36), (98, 130, 30), (130, 152, 24), (152, 164, 17),
             (164, 178, 11), (178, 186, 5), (186, 200, 0)]

    def f(x, yb):
        for a, b, hw in tiers:
            if a <= yb < b:
                return abs(x - c) <= hw
        return False
    return w, h, f


def eiffel():
    w, h, c = 121, 212, 60

    def half(yb):
        return 3 + 57 * (max(0.0, 1 - yb / 170) ** 2.4)

    def f(x, yb):
        dx = abs(x - c)
        if yb >= 196:
            return dx == 0
        if yb >= 170:
            return dx <= (1 if yb > 184 else 2)
        hw = half(yb)
        if 44 <= yb < 49:
            return dx <= hw + 3
        if 108 <= yb < 111:
            return dx <= hw + 2
        if dx > hw:
            return False
        if yb < 44 and (dx / 36) ** 2 + (yb / 39) ** 2 < 1:
            return False
        if 49 <= yb < 108 and dx < hw - 5:
            return False
        return True
    return w, h, f


def colosseum():
    w, h = 211, 78

    def top(x):
        return 78 if x < 125 else 78 - int((x - 125) * 0.38) // 6 * 6

    def f(x, yb):
        if yb >= top(x):
            return False
        if yb >= 66:
            return not ((x - 8) % 30 < 4 and 69 <= yb <= 72)
        ly = yb % 22
        lx = (x - 4) % 15
        if ly >= 17 or x < 3 or x > w - 4:
            return True
        if 3 <= lx <= 11 and ly >= 3 and (ly <= 12 or (lx - 7) ** 2 + (ly - 12) ** 2 <= 16):
            return False
        return True
    return w, h, f


def taj_mahal():
    w, h, c = 191, 134, 95

    def f(x, yb):
        dx = abs(x - c)
        if yb < 8:
            return True
        for mx in (8, w - 9):
            m = abs(x - mx)
            if yb < 104 and (m <= 2 or (m <= 4 and yb in (40, 41, 72, 73, 102, 103))):
                return True
            if 104 <= yb < 112 and m * m + (yb - 104) ** 2 <= 16:
                return True
            if 112 <= yb < 116 and m == 0:
                return True
        if 8 <= yb < 64 and dx <= 48:
            if dx <= 12 and 12 <= yb < 46 and (yb < 34 or dx <= 12 * (46 - yb) / 12):
                return False
            for sx in (c - 32, c + 32):
                s = abs(x - sx)
                for y0 in (12, 36):
                    if s <= 6 and y0 <= yb < y0 + 18 and (yb < y0 + 12 or s <= 6 * (y0 + 18 - yb) / 6):
                        return False
            return True
        if 64 <= yb < 72:
            return dx <= 27
        if 72 <= yb < 118:
            dy = yb - 90
            hw = math.sqrt(max(0, 27 ** 2 - dy * dy)) if dy <= 0 else 27 * max(0.0, math.cos(dy / 28 * math.pi / 2)) ** 0.8
            if dx <= hw:
                return True
        if 118 <= yb < 130 and dx == 0:
            return True
        for sx in (c - 38, c + 38):
            if 64 <= yb < 76 and (x - sx) ** 2 + (yb - 66) ** 2 <= 64:
                return True
            if 76 <= yb < 80 and x == sx:
                return True
        return False
    return w, h, f


def babel_tower():
    w, h, c = 151, 160, 75

    def f(x, yb):
        dx = abs(x - c)
        tier, ly = divmod(yb, 22)
        if tier > 6:
            return dx == 0 and yb < 160
        hw = 75 - tier * 11 - ly * 0.25
        if dx > hw:
            return False
        if 4 <= ly <= 13 and dx < hw - 4 and 3 <= (x - c) % 9 <= 5:
            return ly >= 12 and abs((x - c) % 9 - 4) == 1
        return True
    return w, h, f


MONUMENTS = {
    "pyramid": pyramid, "parthenon": parthenon, "skyscraper": skyscraper,
    "eiffel": eiffel, "colosseum": colosseum, "taj-mahal": taj_mahal,
    "babel": babel_tower,
}


class Brick:
    __slots__ = ("gx", "gy", "runs", "cx", "cy")

    def __init__(self, gx, gy, runs, cx, cy):
        self.gx, self.gy, self.runs, self.cx, self.cy = gx, gy, runs, cx, cy


class Monument:
    def __init__(self, name, rng):
        self.name = name
        w, h, fn = MONUMENTS[name]()
        self.w, self.h = w, h
        mask = [[bool(fn(x, h - 1 - y)) for x in range(w)] for y in range(h)]
        self.rowext = []
        for row in mask:
            xs = [x for x, v in enumerate(row) if v]
            self.rowext.append((xs[0], xs[-1]) if xs else None)
        bricks = []
        for gy in range(-(-h // BH)):
            ybot = h - 1 - gy * BH
            ys = [y for y in range(ybot, ybot - BH, -1) if y >= 0]
            for gx in range(-(-w // BW)):
                runs = []
                for y in ys:
                    x, xe = gx * BW, min(w, gx * BW + BW)
                    while x < xe:
                        if mask[y][x]:
                            s = x
                            while x < xe and mask[y][x]:
                                x += 1
                            runs.append((s, y, x - s))
                        else:
                            x += 1
                if runs:
                    bricks.append(Brick(gx, gy, runs, gx * BW + BW / 2, ybot - BH / 2 + 1))
        self.bricks = sorted(bricks, key=lambda b: b.gy + rng.uniform(0, 2.2))


# --------------------------------------------------------------------------
# Sprites (3 px wide, 6 px tall, feet on the last row)

def sprite(rows):
    runs = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == "#":
                s = x
                while x < len(row) and row[x] == "#":
                    x += 1
                runs.append((s - 1, y - len(rows), x - s))
            else:
                x += 1
    return runs


WALK = [sprite([".#.", "###", ".#.", ".#.", "#.#", "#.#"]),
        sprite([".#.", "###", ".#.", ".#.", ".#.", ".#."])]
CARRY = [sprite(["####", "#.#", ".#.", ".#.", "#.#", "#.#"]),
         sprite(["####", "#.#", ".#.", ".#.", ".#.", ".#."])]
PANIC = [sprite(["#.#", ".#.", ".#.", ".#.", "#.#", "#.#"]),
         sprite(["#.#", ".#.", ".#.", ".#.", ".#.", ".#."])]
SAUCER = sprite(["....###....", "...#####...", ".#########.", "###########", "..#######.."])
BIRD = [sprite(["#.#", ".#."]), sprite([".#.", "#.#"])]


def fill_runs(cr, runs, ox, oy, scale=1, mirror_w=None):
    for x, y, n in runs:
        if mirror_w is not None:
            x = mirror_w - x - n
        cr.rectangle(ox + x * scale, oy + y * scale, n * scale, scale)
    cr.fill()


# --------------------------------------------------------------------------

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "kind", "life", "bounced", "abduct", "dead")

    def __init__(self, x, y, vx, vy, kind="brick", life=0.0, abduct=False):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.kind, self.life, self.abduct = kind, life, abduct
        self.bounced = self.dead = False


class Worker:
    __slots__ = ("x", "y", "dir", "state", "carry", "t", "speed", "wait", "lucky", "tx", "pile", "jump")

    def __init__(self, x, y, rng):
        self.x, self.y, self.dir = x, y, 1
        self.state, self.carry = "idle", False
        self.t = rng.uniform(0, 5)
        self.speed = rng.uniform(11, 16)
        self.wait = 0.0
        self.lucky = False
        self.tx = x
        self.pile = 0
        self.jump = 0.0

    def walk_to(self, tx, dt, speed=None):
        d = tx - self.x
        step = (speed or self.speed) * dt
        if abs(d) <= step:
            self.x = tx
            return True
        self.dir = 1 if d > 0 else -1
        self.x += step * self.dir
        return False


# --------------------------------------------------------------------------
# Disasters. affect(x, y) says what happens to a brick or worker at (x, y):
# None, a (vx, vy) launch velocity, or ABDUCT.

ABDUCT = "abduct"


class Disaster:
    def __init__(self, w):
        self.w = w
        self.t = 0.0
        self.done = False
        self.shake = 0
        self.flash = 0.0
        self.origin_x = w.W / 2

    def update(self, dt):
        self.t += dt

    def affect(self, x, y):
        return None

    def force(self, p, dt):
        pass

    def draw_back(self, cr):
        pass

    def draw_front(self, cr):
        pass


def kaiju_frames(hk):
    wk = int(hk * 0.9)

    def ell(u, v, cu, cv, ru, rv):
        return ((u - cu) / ru) ** 2 + ((v - cv) / rv) ** 2 <= 1

    blobs = [(.52, .52, .19, .25), (.42, .45, .12, .16), (.34, .30, .10, .12), (.25, .17, .095, .065),
             (.15, .20, .075, .045), (.19, .235, .07, .03), (.31, .43, .07, .025), (.25, .46, .03, .03)]
    tail = [(.64 + .34 * t, .60 + .36 * t - .06 * math.sin(math.pi * t), .10 * (1 - t) + .02)
            for t in (k / 9 for k in range(10))]
    spikes = []
    for k in range(8):
        s = k / 7
        spikes.append((.33 + .45 * s + .006, .13 + .45 * s - .006, .03 + .012 * (k % 2), .04 + .015 * (k % 2)))
    eye = (int(.225 * wk), int(.15 * hk))
    frames = []
    for f in (0, 1):
        legs = [(.37, .48, 1.0), (.56, .67, .97)] if f == 0 else [(.40, .51, .97), (.53, .64, 1.0)]
        runs = []
        for py in range(hk):
            v = (py + .5) / hk
            row = []
            for px in range(wk):
                u = (px + .5) / wk
                val = 0
                if any(ell(u, v, *b) for b in blobs) or any(ell(u, v, cu, cv, r / .9, r) for cu, cv, r in tail):
                    val = 1
                else:
                    for a, b, bottom in legs:
                        toe = .04 if v > bottom - .05 else 0
                        if a - toe <= u <= b and .62 <= v <= bottom:
                            val = 1
                    if not val and any(abs(u - cu) / su + abs(v - cv) / sv <= 1 for cu, cv, su, sv in spikes):
                        val = 2
                if (px, py) == eye:
                    val = 3
                row.append(val)
            x = 0
            while x < wk:
                if row[x]:
                    s, val = x, row[x]
                    while x < wk and row[x] == val:
                        x += 1
                    runs.append((s, py, x - s, val))
                else:
                    x += 1
        frames.append(runs)
    return wk, frames


class Kaiju(Disaster):
    def __init__(self, w):
        super().__init__(w)
        self.hk = int(min(w.H * 0.62, max(85, (w.ground - w.mtop) * 0.8)))
        self.wk, self.frames = kaiju_frames(self.hk)
        self.dir = w.rng.choice((-1, 1))
        self.x = w.W + 5 if self.dir < 0 else -self.wk - 5
        self.origin_x = self.x + self.wk / 2
        self.state, self.st = "enter", 0.0
        self.beam = None

    def front(self):
        return self.x if self.dir < 0 else self.x + self.wk

    def mouth(self):
        mx = .07 * self.wk
        if self.dir > 0:
            mx = self.wk - mx
        return self.x + mx, self.w.ground - self.hk + .205 * self.hk

    def update(self, dt):
        super().update(dt)
        w = self.w
        self.st += dt
        self.shake = 0
        self.beam = None
        if self.state == "enter":
            self.x += self.dir * 24 * dt
            f = self.front()
            if (self.dir < 0 and f <= w.mx1 + 28) or (self.dir > 0 and f >= w.mx0 - 28):
                self.state, self.st = "roar", 0.0
        elif self.state == "roar":
            self.shake = 2
            if self.st > 1.4:
                self.state, self.st = "breath", 0.0
        elif self.state == "breath":
            k = self.st / 2.8
            mx, my = self.mouth()
            ex = (w.mx0 - 30) if self.dir < 0 else (w.mx1 + 30)
            ey = w.mtop + 3 + (w.ground - w.mtop) * 0.55 * k
            self.beam = (mx, my, ex, ey)
            self.shake = 1
            if self.st > 2.8:
                self.state, self.st = "smash", 0.0
        elif self.state == "smash":
            self.x += self.dir * 20 * dt
            if (self.dir < 0 and self.x + self.wk < -5) or (self.dir > 0 and self.x > w.W + 5):
                self.done = True

    def affect(self, x, y):
        rng = self.w.rng
        if self.beam:
            x0, y0, x1, y1 = self.beam
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy) or 1
            t = max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / (ln * ln)))
            if math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)) < 3.5:
                return dx / ln * rng.uniform(60, 120), dy / ln * 90 - rng.uniform(20, 60)
        if self.state in ("enter", "smash"):
            rel = (x - self.x) / self.wk
            if .1 < rel < .9 and y > self.w.ground - self.hk * .9:
                return self.dir * rng.uniform(40, 110), -rng.uniform(30, 120)
        return None

    def draw_front(self, cr):
        moving = self.state in ("enter", "smash")
        frame = self.frames[int(self.t * 3) % 2 if moving else 0]
        bob = (int(self.t * 3) % 2) if moving else 0
        oy = self.w.ground - self.hk + bob
        glow = self.state in ("roar", "breath")
        mw = self.wk if self.dir > 0 else None
        for col, vals in ((SIL, (1,)), (BREATH if glow else SIL, (2,)), (EYE, (3,))):
            cr.set_source_rgb(*col)
            fill_runs(cr, [(x, y, n) for x, y, n, v in frame if v in vals], int(self.x), oy, mirror_w=mw)
        if self.beam:
            x0, y0, x1, y1 = self.beam
            steps = int(math.hypot(x1 - x0, y1 - y0))
            for col, r in ((BREATH, 1), (BREATH_CORE, 0)):
                cr.set_source_rgb(*col)
                for i in range(0, steps, 1):
                    k = i / steps
                    jitter = (i * 7 + int(self.t * 30)) % 3 - 1 if r else 0
                    cr.rectangle(int(x0 + (x1 - x0) * k) - r, int(y0 + (y1 - y0) * k) - r + jitter, 1 + 2 * r, 1 + 2 * r)
                cr.fill()


class Tsunami(Disaster):
    def __init__(self, w):
        super().__init__(w)
        self.dir = w.rng.choice((-1, 1))
        self.hgt = min(w.H * 0.6, max(70, (w.ground - w.mtop) * 0.8))
        self.front = w.W + 40 if self.dir < 0 else -40
        self.origin_x = self.front
        self.level = 1.0

    def depth(self, x):
        return (x - self.front) if self.dir < 0 else (self.front - x)

    def height(self, d):
        if d < 0:
            return 0
        rise = min(1.0, (d + 3) / 10) ** 0.7
        body = 0.42 + 0.58 * math.exp(-((d - 14) / 24) ** 2) + 0.04 * math.sin(d * 0.12 + self.t * 3)
        return self.hgt * self.level * rise * body

    def update(self, dt):
        super().update(dt)
        self.front += self.dir * 72 * dt
        if (self.dir < 0 and self.front < -60) or (self.dir > 0 and self.front > self.w.W + 60):
            self.level -= dt / 4
            if self.level <= 0:
                self.level = 0
                self.done = True

    def affect(self, x, y):
        d = self.depth(x)
        if d >= -6 and y >= self.w.ground - self.height(max(d, 0)) - 2 and self.level > 0.5:
            return self.dir * self.w.rng.uniform(60, 110), -self.w.rng.uniform(10, 50)
        return None

    def force(self, p, dt):
        d = self.depth(p.x)
        if d >= 0 and p.y >= self.w.ground - self.height(d):
            p.vx += (self.dir * 70 * self.level - p.vx) * 2.5 * dt
            p.vy -= GRAVITY * 0.95 * dt
            p.vy *= 1 - 1.5 * dt

    def draw_front(self, cr):
        g = self.w.ground
        crest = []
        cr.set_source_rgb(*WATER)
        for x in range(self.w.W):
            d = self.depth(x)
            h = self.height(d)
            if h >= 1:
                cr.rectangle(x, int(g - h), 1, int(h) + 1)
                crest.append((x, int(g - h), d))
        cr.fill()
        cr.set_source_rgb(*WATER_HI)
        ph = int(self.t * 20)
        for x, y, d in crest:
            for k in range(1, 6):
                yy = y + k * 7 + (k * 3) % 4
                if yy < g and (x + ph * (k % 2 * 2 - 1) + k * 5) % 13 < 4:
                    cr.rectangle(x, yy, 1, 1)
        cr.fill()
        cr.set_source_rgb(*FOAM)
        for x, y, d in crest:
            if d < 28 or (x * 7 + int(self.t * 8)) % 11 == 0:
                cr.rectangle(x, y, 1, 2 if d < 18 else 1)
        if self.level > 0.5:
            peak = g - self.height(14)
            for k in range(0, 12):
                lx = self.front - self.dir * 14 + self.dir * k * 1.6
                cr.rectangle(int(lx), int(peak + k * k * 0.22), 2, max(1, 3 - k // 4))
        cr.fill()


class Meteor(Disaster):
    FALL = 2.2
    R = 115

    def __init__(self, w):
        super().__init__(w)
        rng = w.rng
        self.tx = (w.mx0 + w.mx1) / 2 + rng.uniform(-10, 10)
        self.ty = w.mtop + (w.ground - w.mtop) * 0.35
        side = rng.choice((-1, 1))
        self.sx, self.sy = self.tx + side * w.W * 0.6, -30
        self.origin_x = self.tx
        self.trail = []
        self.ring = -1
        self.impacted = False

    def update(self, dt):
        super().update(dt)
        t = self.t
        if t < self.FALL:
            k = (t / self.FALL) ** 2
            self.trail.append((self.sx + (self.tx - self.sx) * k, self.sy + (self.ty - self.sy) * k))
            self.trail = self.trail[-16:]
        else:
            if not self.impacted:
                self.impacted = True
                for _ in range(30):
                    a = self.w.rng.uniform(0, math.tau)
                    self.w.particles.append(Particle(self.tx, self.ty, math.cos(a) * 20, math.sin(a) * 12 - 10,
                                                     "smoke", life=self.w.rng.uniform(2, 4)))
            e = t - self.FALL
            self.flash = max(0.0, 1 - e / 0.3)
            self.ring = self.R * e / 0.7 if e < 0.7 else -1
            self.shake = 3 if e < 1 else (1 if e < 2 else 0)
            self.trail = []
            if e > 3:
                self.done = True

    def affect(self, x, y):
        if self.ring < 0:
            return None
        d = math.hypot(x - self.tx, y - self.ty)
        if d < self.ring:
            d = max(d, 1)
            s = 170 * (1 - d / self.R) + 30
            return (x - self.tx) / d * s, (y - self.ty) / d * s - 40
        return None

    def draw_front(self, cr):
        n = len(self.trail)
        for i, (x, y) in enumerate(self.trail):
            k = i / max(1, n - 1)
            cr.set_source_rgb(*(FIRE1 if k > .85 else FIRE2 if k > .5 else FIRE3))
            r = 1 + int(k * 2)
            cr.rectangle(int(x) - r // 2, int(y) - r // 2, r, r)
            cr.fill()
        if self.impacted:
            e = self.t - self.FALL
            if e < 0.6:
                r = 16 * (1 - e / 0.6)
                cr.set_source_rgb(*FIRE2)
                cr.arc(self.tx, self.ty, r, 0, math.tau)
                cr.fill()
                cr.set_source_rgb(*FIRE1)
                cr.arc(self.tx, self.ty, r * .55, 0, math.tau)
                cr.fill()
            if self.ring > 0:
                cr.set_source_rgb(*FIRE2)
                for i in range(int(self.ring * 1.5)):
                    a = i / (self.ring * 1.5) * math.tau
                    if i % 2 == 0:
                        cr.rectangle(int(self.tx + math.cos(a) * self.ring), int(self.ty + math.sin(a) * self.ring), 1, 1)
                cr.fill()


class Tornado(Disaster):
    def __init__(self, w):
        super().__init__(w)
        self.dir = w.rng.choice((-1, 1))
        self.bx = -40 if self.dir > 0 else w.W + 40
        self.origin_x = self.bx
        self.ht = w.ground * 0.92

    def cx(self, yrel):
        return self.bx + math.sin(yrel * 0.045 + self.t * 2.2) * 5 * (yrel / self.ht) + math.sin(self.t * 0.9) * 3

    def width(self, yrel):
        return 2.5 + (yrel / self.ht) ** 1.5 * 42

    def update(self, dt):
        super().update(dt)
        mid = (self.w.mx0 + self.w.mx1) / 2
        slow = abs(self.bx - mid) < 30
        self.bx += self.dir * (11 if slow else 24) * dt
        if (self.dir > 0 and self.bx > self.w.W + 60) or (self.dir < 0 and self.bx < -60):
            self.done = True

    def affect(self, x, y):
        yrel = self.w.ground - y
        if 0 <= yrel <= self.ht and abs(x - self.cx(yrel)) <= self.width(yrel) + 2:
            return self.w.rng.uniform(-90, 90), -self.w.rng.uniform(80, 170)
        return None

    def force(self, p, dt):
        yrel = self.w.ground - p.y
        if 0 <= yrel <= self.ht:
            c = self.cx(yrel)
            if abs(p.x - c) <= self.width(yrel) + 4:
                p.vy -= 330 * dt
                p.vx = (c - p.x) * 2.0 + math.sin(self.t * 6 + p.y * 0.2) * 90 + self.dir * 20

    def draw_front(self, cr):
        g = self.w.ground
        rows = []
        for yrel in range(int(self.ht)):
            rows.append((g - yrel, self.cx(yrel), self.width(yrel)))
        cr.set_source_rgb(*FUNNEL)
        for y, c, wd in rows:
            cr.rectangle(int(c - wd), y, int(2 * wd) + 1, 1)
        cr.fill()
        cr.set_source_rgb(*FUNNEL_HI)
        ph = self.t * 40
        for y, c, wd in rows:
            span = 2 * wd
            n = int(span / 9) + 1
            for j in range(n):
                s = (y * 0.8 + ph + j * 9) % span - wd
                cr.rectangle(int(c + s), y, 2, 1)
        cr.fill()
        cr.set_source_rgb(*SMOKE)
        for i in range(24):
            a = i / 24 * math.tau + self.t * 3
            cr.rectangle(int(self.bx + math.cos(a) * 14), int(g - 2 - abs(math.sin(a)) * 4), 2, 2)
        cr.fill()


class Quake(Disaster):
    def __init__(self, w):
        super().__init__(w)
        self.origin_x = (w.mx0 + w.mx1) / 2
        self.based = False

    def update(self, dt):
        super().update(dt)
        w = self.w
        self.shake = 2 if self.t < 5 else (1 if self.t < 6 else 0)
        if self.t < 5:
            standing = list(w.standing.values())
            if standing:
                top = sorted(standing, key=lambda b: -b.gy)[:max(1, len(standing) // 2)]
                for b in w.rng.sample(top, min(len(top), max(1, len(standing) // 60))):
                    w.knock(b, w.rng.uniform(-15, 15), 0)
            if w.rng.random() < 0.5:
                x = w.rng.uniform(w.mx0, w.mx1)
                w.particles.append(Particle(x, w.ground - 1, w.rng.uniform(-8, 8), -6, "smoke", life=2.5))
        if self.t > 4.5 and not self.based:
            self.based = True
            for b in list(w.standing.values()):
                if b.gy <= 1:
                    w.knock(b, w.rng.uniform(-10, 10), 0)
        if self.t > 7:
            self.done = True


class UFO(Disaster):
    def __init__(self, w):
        super().__init__(w)
        side = w.rng.choice((-1, 1))
        self.start = (w.W / 2 + side * (w.W / 2 + 30), 20.0)
        self.hover = ((w.mx0 + w.mx1) / 2, max(16.0, w.mtop - 30))
        self.ux, self.uy = self.start
        self.origin_x = self.hover[0]
        self.beam_on = False

    def update(self, dt):
        super().update(dt)
        t = self.t
        sx, sy = self.start
        hx, hy = self.hover
        self.beam_on = 3.8 < t < 9.5
        if t < 3:
            k = 1 - (1 - t / 3) ** 3
            self.ux, self.uy = sx + (hx - sx) * k, sy + (hy - sy) * k + math.sin(t * 4) * 2
        elif t < 10:
            self.ux, self.uy = hx + math.sin(t * 1.3) * 3, hy + math.sin(t * 2.1) * 1.5
        else:
            k = (t - 10) / 1.6
            self.ux, self.uy = hx + (sx - hx) * k * k, hy - 120 * k * k
            if k >= 1:
                self.done = True

    def halfw(self, y):
        return 4 + (y - self.uy) * 0.24

    def affect(self, x, y):
        if self.beam_on and y > self.uy and abs(x - self.ux) <= self.halfw(y):
            return ABDUCT
        return None

    def force(self, p, dt):
        if p.abduct:
            p.vx = (self.ux - p.x) * 1.2
            p.vy = -36 - (p.life * 3)
            p.life += dt
            if p.y <= self.uy + 3:
                p.dead = True

    def draw_back(self, cr):
        if self.beam_on:
            g = self.w.ground
            on = 0.24 + 0.06 * math.sin(self.t * 9)
            for y in range(int(self.uy) + 4, int(g)):
                hw = self.halfw(y)
                cr.set_source_rgba(*BEAM, on)
                cr.rectangle(int(self.ux - hw), y, int(2 * hw) + 1, 1)
                cr.fill()

    def draw_front(self, cr):
        x, y = int(self.ux) - 11, int(self.uy) - 4
        cr.set_source_rgb(*SIL)
        fill_runs(cr, SAUCER, x, y + 10, scale=2)
        cr.set_source_rgb(*UFO_LIGHT)
        for i in range(5):
            if (i + int(self.t * 6)) % 3 == 0:
                cr.rectangle(x + 3 + i * 4, y + 6, 2, 2)
        cr.fill()


DISASTERS = {"kaiju": Kaiju, "tsunami": Tsunami, "meteor": Meteor,
             "tornado": Tornado, "earthquake": Quake, "ufo": UFO}


# --------------------------------------------------------------------------

class World:
    def __init__(self, W, H, seed, speed=1.0, first_monument=None):
        self.W, self.H = W, H
        self.speed = speed
        self.rng = random.Random(seed)
        self.ground = H - max(14, H // 12)
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        self.cr = cairo.Context(self.surf)
        self.cr.set_antialias(cairo.ANTIALIAS_NONE)
        self.particles = []
        self.workers = []
        self.birds = []
        self.hm = [0] * (W + 2)
        self.rubble = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        self.rubble_dirty = True
        self.disaster = None
        self.recent_disasters = []
        order = list(MONUMENTS)
        self.rng.shuffle(order)
        if first_monument:
            order.remove(first_monument)
            order.insert(0, first_monument)
        self.order = order
        self.next_mon = 0
        self.collapse_t = 0.0
        self.t = 0.0
        self.make_static()
        self.stars = [(self.rng.randrange(W), self.rng.randrange(int(self.ground * 0.4)), self.rng.random() < 0.3)
                      for _ in range(W // 9)]
        for _ in range(WORKERS):
            self.workers.append(Worker(self.rng.uniform(W * .2, W * .8), self.ground, self.rng))
        self.start_build(progress=self.rng.uniform(0.15, 0.6))

    # ---- static layers ----
    def make_static(self):
        W, H, g, rng = self.W, self.H, self.ground, self.rng
        self.sky = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        cr = cairo.Context(self.sky)
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        n = len(SKY)
        for y in range(g):
            f = y / g * (n - 1)
            i = int(f)
            frac = f - i
            cr.set_source_rgb(*SKY[i])
            cr.rectangle(0, y, W, 1)
            cr.fill()
            if frac > 0.72 and i + 1 < n:
                cr.set_source_rgb(*SKY[i + 1])
                for x in range(y % 2, W, 2):
                    cr.rectangle(x, y, 1, 1)
                cr.fill()
        # sun with retro stripes
        sx, sy, r = W * rng.uniform(0.35, 0.65), g - 50, 38
        for dy in range(-r, r + 1):
            if dy > 5 and (dy - 6) % 7 < 1 + (dy - 6) // 9:
                continue
            hw = math.sqrt(r * r - dy * dy)
            cr.set_source_rgb(*(SUN_HI if dy < 0 else SUN_LO))
            cr.rectangle(int(sx - hw), int(sy + dy), int(2 * hw) + 1, 1)
            cr.fill()
        a, b, c = (rng.uniform(0, 6) for _ in range(3))
        for col, base, amp in ((HILL_FAR, 30, 1.0), (HILL_NEAR, 12, 0.55)):
            cr.set_source_rgb(*col)
            for x in range(W):
                hh = base + amp * (10 * math.sin(x * .013 + a) + 6 * math.sin(x * .031 + b) + 3 * math.sin(x * .09 + c))
                cr.rectangle(x, int(g - hh), 1, int(hh) + 1)
            cr.fill()
            a, b, c = a + 2, b + 1, c + 3
        # cypress trees near the edges
        cr.set_source_rgb(*SIL)
        for _ in range(rng.randint(3, 6)):
            x = rng.choice((rng.uniform(4, W * .18), rng.uniform(W * .82, W - 4)))
            th, tw = rng.randint(16, 32), rng.uniform(4, 7)
            for yy in range(th):
                hw = tw / 2 * math.sin(math.pi * (yy + 1) / (th + 1)) ** 0.6
                cr.rectangle(int(x - hw), g - 2 - yy, max(1, int(2 * hw)), 1)
            cr.rectangle(int(x), g - 2, 1, 2)
            cr.fill()
        # ground
        self.fg = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        cr = cairo.Context(self.fg)
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgb(*SIL)
        cr.rectangle(0, g, W, H - g)
        for x in range(W):
            if rng.random() < 0.18:
                cr.rectangle(x, g - rng.randint(1, 2), 1, 2)
        cr.fill()

    # ---- monument lifecycle ----
    def start_build(self, progress=0.0):
        name = self.order[self.next_mon % len(self.order)]
        self.next_mon += 1
        m = self.mon = Monument(name, self.rng)
        margin = m.w / 2 + 36
        mx = self.W / 2 + self.rng.uniform(-self.W * .08, self.W * .08)
        mx = max(margin, min(self.W - margin, mx))
        self.ox, self.oy = int(mx - m.w / 2), self.ground - m.h
        self.mx0, self.mx1, self.mtop = self.ox, self.ox + m.w, self.oy
        bottom = m.rowext[-1]
        self.site = (self.ox + bottom[0], self.ox + bottom[1])
        self.piles = (self.site[0] - 22, self.site[1] + 22)
        self.msurf = cairo.ImageSurface(cairo.FORMAT_ARGB32, m.w, m.h)
        self.mcr = cairo.Context(self.msurf)
        self.mcr.set_antialias(cairo.ANTIALIAS_NONE)
        self.standing = {}
        self.placed = 0
        self.coltop = [self.ground] * (self.W + 2)
        self.build_acc = 0.0
        self.phase, self.phase_t = "build", 0.0
        self.disaster = None
        self.hm = [0] * (self.W + 2)
        self.rubble_dirty = True
        for _ in range(int(len(m.bricks) * progress)):
            self.place_next()
        for i, wk in enumerate(self.workers):
            wk.state = "top" if i < 3 else "haul"
            wk.pile = i % 2
            wk.carry = self.rng.random() < .5
            wk.y = self.ground

    def place_next(self):
        b = self.mon.bricks[self.placed]
        self.placed += 1
        self.standing[(b.gx, b.gy)] = b
        self.mcr.set_source_rgb(*SIL)
        fill_runs(self.mcr, b.runs, 0, 0)
        for x, y, n in b.runs:
            for xx in range(self.ox + x, self.ox + x + n):
                if 0 <= xx < self.W:
                    self.coltop[xx] = min(self.coltop[xx], self.oy + y)

    def knock(self, b, vx, vy=None, abduct=False):
        key = (b.gx, b.gy)
        if key not in self.standing:
            return
        del self.standing[key]
        self.mcr.set_operator(cairo.OPERATOR_CLEAR)
        fill_runs(self.mcr, b.runs, 0, 0)
        self.mcr.set_operator(cairo.OPERATOR_OVER)
        self.particles.append(Particle(self.ox + b.cx, self.oy + b.cy, vx or 0, vy or 0, "brick", abduct=abduct))

    def collapse_check(self):
        alive = self.standing
        seen = {k for k in alive if k[1] == 0}
        stack = list(seen)
        while stack:
            gx, gy = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    k = (gx + dx, gy + dy)
                    if k in alive and k not in seen:
                        seen.add(k)
                        stack.append(k)
        for k in [k for k in alive if k not in seen]:
            self.knock(alive[k], self.rng.uniform(-8, 8), self.rng.uniform(-5, 5))

    def begin_disaster(self, name=None):
        if name is None:
            options = [n for n in DISASTERS if n not in self.recent_disasters] or list(DISASTERS)
            name = self.rng.choice(options)
        self.recent_disasters = (self.recent_disasters + [name])[-2:]
        self.disaster = DISASTERS[name](self)
        self.phase, self.phase_t = "disaster", 0.0
        lucky = self.rng.sample(self.workers, min(len(self.workers), self.rng.randint(3, 5)))
        for wk in self.workers:
            wk.lucky = wk in lucky
            wk.state = "panic"
            wk.y = self.ground
            wk.carry = False
            wk.dir = 1 if wk.x > self.disaster.origin_x else -1
            wk.speed = self.rng.uniform(26, 36) * (1.3 if wk.lucky else 1)

    # ---- simulation ----
    def update(self, dt):
        dt *= self.speed
        self.t += dt
        self.phase_t += dt
        rng = self.rng
        if self.phase == "build":
            n = len(self.mon.bricks)
            self.build_acc += dt * n / BUILD_TIME
            while self.build_acc >= 1 and self.placed < n:
                self.build_acc -= 1
                self.place_next()
            if self.placed >= n:
                self.phase, self.phase_t = "admire", 0.0
                for wk in self.workers:
                    wk.state, wk.carry, wk.y = "idle", False, self.ground
        elif self.phase == "admire":
            if self.phase_t > ADMIRE_TIME:
                self.begin_disaster()
        elif self.phase == "disaster":
            d = self.disaster
            d.update(dt)
            for b in list(self.standing.values()):
                r = d.affect(self.ox + b.cx, self.oy + b.cy)
                if r == ABDUCT:
                    self.knock(b, 0, 0, abduct=True)
                elif r:
                    self.knock(b, *r)
            for wk in list(self.workers):
                if wk.state == "hidden" or wk.lucky:
                    continue
                r = d.affect(wk.x, wk.y - 3)
                if r:
                    self.workers.remove(wk)
                    vx, vy = (0, 0) if r == ABDUCT else r
                    self.particles.append(Particle(wk.x, wk.y - 3, vx, vy, "body", abduct=r == ABDUCT))
            self.collapse_t += dt
            if self.collapse_t > 0.3:
                self.collapse_t = 0
                self.collapse_check()
            if d.done:
                self.phase, self.phase_t = "aftermath", 0.0
        elif self.phase == "aftermath":
            if self.standing:
                top = sorted(self.standing.values(), key=lambda b: -b.gy)
                for b in top[:max(3, len(top) // 10)]:
                    self.knock(b, rng.uniform(-12, 12), 0)
            settled = not self.standing and not any(p.kind != "smoke" for p in self.particles)
            if (settled and self.phase_t > 2) or self.phase_t > 12:
                self.disaster = None
                self.phase, self.phase_t = "recover", 0.0
                self.hm0 = list(self.hm)
                for wk in self.workers:
                    wk.state = "return"
                    wk.lucky = False
                    wk.speed = rng.uniform(11, 16)
                    wk.tx = rng.uniform(self.mx0, self.mx1)
                self.spawn_t = 0.0
        elif self.phase == "recover":
            k = max(0.0, 1 - self.phase_t / (RECOVER_TIME * 0.85))
            self.hm = [int(h * k) for h in self.hm0]
            self.rubble_dirty = True
            self.spawn_t += dt
            if len(self.workers) < WORKERS and self.spawn_t > RECOVER_TIME / (WORKERS + 2):
                self.spawn_t = 0
                side = rng.choice((-6, self.W + 6))
                wk = Worker(side, self.ground, rng)
                wk.state, wk.tx = "return", rng.uniform(self.mx0, self.mx1)
                self.workers.append(wk)
            if self.phase_t > RECOVER_TIME:
                self.start_build()
        self.update_workers(dt)
        self.update_particles(dt)
        self.update_birds(dt)
        if self.rubble_dirty:
            self.draw_rubble()

    def update_workers(self, dt):
        rng, g = self.rng, self.ground
        recent = self.mon.bricks[max(0, self.placed - 30):self.placed]
        for wk in self.workers:
            wk.t += dt
            if wk.jump > 0:
                wk.jump = max(0.0, wk.jump - dt)
            s = wk.state
            if s == "haul":
                site = self.site[wk.pile] + (-2 if wk.pile == 0 else 2)
                pile = self.piles[wk.pile]
                if wk.wait > 0:
                    wk.wait -= dt
                elif wk.walk_to(site if wk.carry else pile, dt):
                    wk.carry = not wk.carry
                    wk.wait = rng.uniform(0.3, 1.2)
            elif s == "top":
                if wk.wait <= 0 and recent:
                    b = rng.choice(recent)
                    wk.tx = self.ox + b.cx + rng.uniform(-2, 2)
                    wk.wait = rng.uniform(2.5, 5)
                wk.wait -= dt
                wk.walk_to(wk.tx, dt, 7)
                xi = min(self.W - 1, max(0, int(wk.x)))
                wk.y = self.coltop[xi]
            elif s == "idle":
                if wk.wait <= 0:
                    wk.tx = rng.uniform(self.mx0 - 30, self.mx1 + 30)
                    wk.wait = rng.uniform(3, 9)
                    if self.phase == "admire" and rng.random() < .4:
                        wk.jump = 1.2
                wk.wait -= dt
                if wk.jump <= 0:
                    wk.walk_to(wk.tx, dt, 6)
            elif s == "panic":
                wk.x += wk.dir * wk.speed * dt
                if wk.x < -6 or wk.x > self.W + 6:
                    wk.state = "hidden"
            elif s == "return":
                if wk.walk_to(wk.tx, dt):
                    wk.state, wk.wait = "idle", rng.uniform(1, 4)
            wk.y = wk.y if s == "top" else g

    def update_particles(self, dt):
        d, g, hm = self.disaster, self.ground, self.hm
        alive = []
        for p in self.particles:
            if p.kind == "smoke":
                p.life -= dt
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.vx *= 1 - dt
                p.vy = p.vy * (1 - dt) - 4 * dt
                if p.life > 0:
                    alive.append(p)
                continue
            if p.abduct:
                if d:
                    d.force(p, dt)
                else:
                    p.abduct = False
            else:
                p.vy += GRAVITY * dt
                if d:
                    d.force(p, dt)
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.dead or p.x < -10 or p.x > self.W + 10 or p.y > self.H + 10 or p.y < -80:
                continue
            ix = min(self.W - 1, max(0, int(p.x)))
            floor = g - hm[ix]
            if p.y >= floor and p.vy > 0 and not p.abduct:
                if not p.bounced and p.vy > 90:
                    p.bounced = True
                    p.vy *= -0.25
                    p.vx *= 0.5
                    p.y = floor - 0.1
                else:
                    if p.kind == "brick":
                        hm[ix] += 2
                        hm[ix + 1] += 1
                    else:
                        hm[ix] += 1
                    self.rubble_dirty = True
                    continue
            alive.append(p)
        self.particles = alive
        if self.rubble_dirty:
            for _ in range(3):
                for x in range(self.W):
                    diff = hm[x] - hm[x + 1]
                    if diff > 2:
                        hm[x] -= 1
                        hm[x + 1] += 1
                    elif diff < -2:
                        hm[x] += 1
                        hm[x + 1] -= 1

    def update_birds(self, dt):
        rng = self.rng
        if not self.birds and rng.random() < dt / 25:
            d = rng.choice((-1, 1))
            x0 = -10 if d > 0 else self.W + 10
            y0 = rng.uniform(25, self.ground * .45)
            self.birds = [[x0 - d * i * rng.uniform(6, 10), y0 + rng.uniform(-6, 6), d, rng.uniform(0, 1)]
                          for i in range(rng.randint(2, 6))]
        for b in self.birds:
            b[0] += b[2] * 16 * dt
            b[3] += dt
        self.birds = [b for b in self.birds if -40 < b[0] < self.W + 40]

    # ---- drawing ----
    def draw_rubble(self):
        cr = cairo.Context(self.rubble)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgb(*SIL)
        for x in range(self.W):
            h = self.hm[x]
            if h > 0:
                cr.rectangle(x, self.ground - h, 1, h)
        cr.fill()
        self.rubble_dirty = False

    def draw_scaffold(self, cr):
        if self.placed == 0 or self.phase != "build":
            return
        m = self.mon
        top = min(self.coltop[self.mx0:self.mx1 + 1])
        cr.set_source_rgb(*SIL)
        prev = None
        for y in range(self.ground - 1, top - 6, -7):
            ly = y - self.oy
            if not (0 <= ly < m.h) or m.rowext[ly] is None:
                continue
            l, r = self.ox + m.rowext[ly][0], self.ox + m.rowext[ly][1]
            cr.rectangle(l - 6, y, 6, 1)
            cr.rectangle(r + 1, y, 6, 1)
            if prev:
                pl, pr, py = prev
                cr.rectangle(l - 5, y, 1, py - y)
                cr.rectangle(r + 5, y, 1, py - y)
            prev = (l, r, y)
        cr.fill()

    def draw_workers(self, cr):
        cr.set_source_rgb(*SIL)
        for wk in self.workers:
            if wk.state == "hidden":
                continue
            frame = int(wk.t * 6) % 2
            x, y = int(wk.x), int(wk.y)
            if wk.state == "panic":
                runs = PANIC[frame]
            elif wk.jump > 0:
                runs = PANIC[0]
                y -= int(abs(math.sin(wk.jump * 8)) * 3)
            elif wk.state == "haul" and wk.carry:
                runs = CARRY[frame if wk.wait <= 0 else 1]
            elif wk.state == "top":
                runs = WALK[1]
                cr.rectangle(x + (2 if wk.dir > 0 else -2), y - (5 if frame else 4), 1, 1)
            elif wk.state == "idle" and abs(wk.tx - wk.x) < 1:
                runs = WALK[1]
            else:
                runs = WALK[frame if wk.wait <= 0 else 1]
            for dx, dy, n in runs:
                cr.rectangle(x + dx, y + dy, n, 1)
        cr.fill()
        if self.phase == "build":
            cr.set_source_rgb(*FIRE2)
            for wk in self.workers:
                if wk.state == "top" and int(wk.t * 6) % 6 == 0:
                    cr.rectangle(int(wk.x) + 2 * wk.dir, int(wk.y) - 1, 1, 1)
            cr.fill()

    def draw_piles(self, cr):
        if self.phase != "build":
            return
        left = 1 - self.placed / max(1, len(self.mon.bricks))
        ph = 2 + int(9 * left)
        cr.set_source_rgb(*SIL)
        for px in self.piles:
            for i in range(ph):
                inset = max(0, i - ph + 3)
                cr.rectangle(int(px) - 5 + inset, self.ground - 1 - i, 10 - 2 * inset, 1)
        cr.fill()

    def draw_particles(self, cr):
        cr.set_source_rgb(*SIL)
        for p in self.particles:
            if p.kind == "brick":
                cr.rectangle(int(p.x), int(p.y), 2, 2)
            elif p.kind == "body":
                if int(self.t * 8 + p.x) % 2:
                    cr.rectangle(int(p.x), int(p.y) - 1, 1, 3)
                else:
                    cr.rectangle(int(p.x) - 1, int(p.y), 3, 1)
        cr.fill()
        for p in self.particles:
            if p.kind == "smoke":
                cr.set_source_rgba(*SMOKE, min(1.0, p.life / 2))
                cr.rectangle(int(p.x), int(p.y), 2, 2)
                cr.fill()

    def render(self):
        cr = self.cr
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_surface(self.sky, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_rgb(*STAR)
        for i, (x, y, tw) in enumerate(self.stars):
            if not tw or int(self.t * 1.5 + i * 7) % 5:
                cr.rectangle(x, y, 1, 1)
        cr.fill()
        cr.set_source_rgb(*SIL)
        for bx, by, bd, bt in self.birds:
            fill_runs(cr, BIRD[int(bt * 4) % 2], int(bx), int(by))
        d = self.disaster
        shake = d.shake if d else 0
        cr.save()
        if shake:
            cr.translate(self.rng.randint(-shake, shake), self.rng.randint(-shake // 2, shake // 2))
        if d:
            d.draw_back(cr)
        cr.set_source_surface(self.msurf, self.ox, self.oy)
        cr.paint()
        self.draw_scaffold(cr)
        self.draw_piles(cr)
        cr.set_source_surface(self.rubble, 0, 0)
        cr.paint()
        self.draw_workers(cr)
        self.draw_particles(cr)
        cr.set_source_surface(self.fg, 0, 0)
        cr.paint()
        if d:
            d.draw_front(cr)
        cr.restore()
        if d and d.flash > 0:
            cr.set_source_rgba(*FIRE1, d.flash * 0.7)
            cr.paint()
        self.surf.flush()
        return self.surf


# --------------------------------------------------------------------------

def art_size(dev_w, dev_h):
    px = max(1, round(dev_h / ART_H))
    return -(-dev_w // px), -(-dev_h // px)


def snapshot(args):
    W, H = art_size(3840, 2160)
    world = World(W, H, seed=args.seed, speed=1.0, first_monument=args.monument)
    if args.monument:
        world.next_mon = 0
        world.start_build(progress=args.progress)
    if args.disaster:
        while world.placed < len(world.mon.bricks):
            world.place_next()
        world.begin_disaster(args.disaster)
    step = 1 / FPS
    for _ in range(int(args.at * FPS)):
        world.update(step)
    surf = world.render()
    scale = args.scale
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, W * scale, H * scale)
    cr = cairo.Context(out)
    cr.scale(scale, scale)
    cr.set_source_surface(surf, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.paint()
    out.write_to_png(args.snapshot)
    print(f"{args.snapshot}: {W * scale}x{H * scale} phase={world.phase} monument={world.mon.name}")


def run_gtk(args):
    lib = "/usr/lib/libgtk4-layer-shell.so"
    if not args.window and lib not in os.environ.get("LD_PRELOAD", ""):
        env = dict(os.environ, LD_PRELOAD=(lib + " " + os.environ.get("LD_PRELOAD", "")).strip())
        os.execve(sys.executable, [sys.executable] + sys.argv, env)

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Gsk", "4.0")
    gi.require_version("Graphene", "1.0")
    gi.require_foreign("cairo")
    from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk
    if not args.window:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as Layer

    class Canvas(Gtk.Widget):
        def __init__(self, world):
            super().__init__()
            self.world = world
            self.texture = None

        def frame(self, dt):
            self.world.update(dt)
            s = self.world.render()
            data = GLib.Bytes.new(bytes(s.get_data()))
            self.texture = Gdk.MemoryTexture.new(s.get_width(), s.get_height(),
                                                 Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, data, s.get_stride())
            self.queue_draw()

        def do_snapshot(self, snap):
            if self.texture:
                rect = Graphene.Rect().init(0, 0, self.get_width(), self.get_height())
                snap.append_scaled_texture(self.texture, Gsk.ScalingFilter.NEAREST, rect)

    app = Gtk.Application(application_id=None)
    canvases, windows = [], []

    def build(*_):
        for w in windows:
            w.destroy()
        windows.clear()
        canvases.clear()
        if args.window:
            W, H = art_size(1920, 1080)
            win = Gtk.Window(application=app, title="Babel")
            win.set_default_size(1280, 720)
            c = Canvas(World(W, H, seed=int(time.time()), speed=args.speed, first_monument=args.monument))
            win.set_child(c)
            win.present()
            windows.append(win)
            canvases.append(c)
            return
        monitors = Gdk.Display.get_default().get_monitors()
        for i in range(monitors.get_n_items()):
            mon = monitors.get_item(i)
            geo = mon.get_geometry()
            scale = mon.get_scale() if hasattr(mon, "get_scale") else mon.get_scale_factor()
            W, H = art_size(round(geo.width * scale), round(geo.height * scale))
            first = args.monument if i == 0 else None
            world = World(W, H, seed=int(time.time()) * 31 + i, speed=args.speed, first_monument=first)
            world.next_mon = i % len(world.order) if not first else 0
            world.start_build(progress=world.rng.uniform(0.15, 0.6))
            win = Gtk.Window(application=app)
            Layer.init_for_window(win)
            Layer.set_layer(win, Layer.Layer.BOTTOM)
            Layer.set_namespace(win, "babel-live")
            Layer.set_monitor(win, mon)
            for edge in (Layer.Edge.TOP, Layer.Edge.BOTTOM, Layer.Edge.LEFT, Layer.Edge.RIGHT):
                Layer.set_anchor(win, edge, True)
            Layer.set_exclusive_zone(win, -1)
            Layer.set_keyboard_mode(win, Layer.KeyboardMode.NONE)
            c = Canvas(world)
            win.set_child(c)
            win.present()
            win.get_surface().set_input_region(cairo.Region())
            windows.append(win)
            canvases.append(c)

    last = [time.monotonic()]

    def tick():
        now = time.monotonic()
        dt = min(0.25, now - last[0])
        last[0] = now
        for c in canvases:
            c.frame(dt)
        return True

    def activate(app):
        app.hold()
        build()
        if not args.window:
            Gdk.Display.get_default().get_monitors().connect("items-changed", lambda *a: GLib.timeout_add(1500, lambda: build() and False))
        GLib.timeout_add(int(1000 / FPS), tick)
        try:
            gi.require_version("GLibUnix", "2.0")
            from gi.repository import GLibUnix
            signal_add = GLibUnix.signal_add
        except (ImportError, ValueError):
            signal_add = GLib.unix_signal_add
        for sig in (2, 15):
            signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: app.quit() or False)

    app.connect("activate", activate)
    app.run([])


def main():
    ap = argparse.ArgumentParser(description="Babel live wallpaper")
    ap.add_argument("--window", action="store_true")
    ap.add_argument("--snapshot")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--monument", choices=list(MONUMENTS))
    ap.add_argument("--disaster", choices=list(DISASTERS))
    ap.add_argument("--progress", type=float, default=0.7)
    ap.add_argument("--at", type=float, default=4.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scale", type=int, default=8)
    args = ap.parse_args()
    if args.snapshot:
        snapshot(args)
    else:
        run_gtk(args)


if __name__ == "__main__":
    main()
