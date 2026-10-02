"""Disasters. Each one says, through affect(x, y), what happens to a block or a
worker at (x, y) this frame: None, a launch velocity (vx, vy), or ABDUCT.
Distances are in art pixels of a 720-row scene (scaled by u for other sizes).
"""

import math

import cairo

ABDUCT = "abduct"


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


WATER, WATER_DEEP, FOAM = hexc("#1d3550"), hexc("#0c1626"), hexc("#e8f1f6")
FIRE1, FIRE2, FIRE3 = hexc("#fff6cf"), hexc("#ffb347"), hexc("#e2532c")
BREATH, BREATH_CORE = hexc("#6fd8ff"), hexc("#f0fcff")
BEAM = hexc("#a6f7dc")
EYE = hexc("#ff4a2e")
FUNNEL = hexc("#2a2735")
UFO_LIGHT = hexc("#ffe066")


class Disaster:
    def __init__(self, w):
        self.w = w
        self.u = w.H / 720
        self.t = 0.0
        self.done = False
        self.shake = 0.0
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


# ---------------------------------------------------------------- kaiju

def kaiju_masks(hk):
    """Two walking frames (body, glowing spikes) as A8 surfaces, facing left."""
    wk = int(hk * .9)
    frames = []
    for f in (0, 1):
        body = cairo.ImageSurface(cairo.FORMAT_A8, wk, hk)
        spikes = cairo.ImageSurface(cairo.FORMAT_A8, wk, hk)
        cr = cairo.Context(body)
        cr.scale(wk, hk)

        def ell(cu, cv, ru, rv, ctx=cr):
            ctx.save()
            ctx.translate(cu, cv)
            ctx.scale(ru, rv)
            ctx.arc(0, 0, 1, 0, math.tau)
            ctx.restore()
            ctx.fill()

        for b in [(.52, .52, .19, .25), (.42, .45, .12, .16), (.34, .30, .10, .12), (.25, .17, .095, .065),
                  (.15, .20, .075, .045), (.19, .235, .07, .03), (.31, .43, .07, .025), (.25, .46, .03, .03)]:
            ell(*b)
        for k in range(14):
            t = k / 13
            r = .10 * (1 - t) + .018
            ell(.64 + .34 * t, .60 + .36 * t - .06 * math.sin(math.pi * t), r / .9, r)
        legs = [(.37, .48, 1.0), (.56, .67, .97)] if f == 0 else [(.40, .51, .97), (.53, .64, 1.0)]
        for a, b, bottom in legs:
            m = (a + b) / 2
            ell(m + .01, .70, (b - a) * .75, .11)
            cr.move_to(a + .005, .74)
            cr.line_to(b - .005, .74)
            cr.line_to(b - .01, bottom - .03)
            cr.line_to(a + .01, bottom - .03)
            cr.close_path()
            cr.fill()
            ell(m - .03, bottom - .025, (b - a) * .75, .025)
        sc = cairo.Context(spikes)
        sc.scale(wk, hk)
        for k in range(8):
            s = k / 7
            cu, cv = .33 + .45 * s + .006, .13 + .45 * s - .006
            su, sv = .03 + .012 * (k % 2), .04 + .015 * (k % 2)
            sc.move_to(cu - su, cv)
            sc.line_to(cu, cv - sv)
            sc.line_to(cu + su, cv)
            sc.line_to(cu, cv + sv)
            sc.close_path()
        sc.fill()
        frames.append((body, spikes))
    return wk, frames


class Kaiju(Disaster):
    def __init__(self, w):
        super().__init__(w)
        self.hk = int(min(w.H * .62, max(230 * self.u, (w.ground - w.mtop) * .8)))
        self.wk, self.frames = kaiju_masks(self.hk)
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
        w, u = self.w, self.u
        self.st += dt
        self.shake = 0
        self.beam = None
        if self.state == "enter":
            self.x += self.dir * 60 * u * dt
            f = self.front()
            if (self.dir < 0 and f <= w.mx1 + 70 * u) or (self.dir > 0 and f >= w.mx0 - 70 * u):
                self.state, self.st = "roar", 0.0
        elif self.state == "roar":
            self.shake = 4 * u
            if self.st > 1.5:
                self.state, self.st = "breath", 0.0
        elif self.state == "breath":
            k = self.st / 3.0
            mx, my = self.mouth()
            ex = (w.mx0 - 80 * u) if self.dir < 0 else (w.mx1 + 80 * u)
            ey = w.mtop + 8 * u + (w.ground - w.mtop) * .55 * k
            ex, ey, hit = clip_beam(w, mx, my, ex, ey, 7 * u)
            if hit:
                scorch(w, ex, ey, u)
            self.beam = (mx, my, ex, ey)
            self.shake = 2 * u
            if self.st > 3.0:
                self.state, self.st = "smash", 0.0
        elif self.state == "smash":
            self.x += self.dir * 50 * u * dt
            if (self.dir < 0 and self.x + self.wk < -5) or (self.dir > 0 and self.x > w.W + 5):
                self.done = True

    def affect(self, x, y):
        rng, u = self.w.rng, self.u
        if self.beam:
            x0, y0, x1, y1 = self.beam
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy) or 1
            t = max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / (ln * ln)))
            if math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)) < 9 * u:
                return dx / ln * rng.uniform(160, 320) * u, (dy / ln * 240 - rng.uniform(50, 160)) * u
        if self.state in ("enter", "smash"):
            rel = (x - self.x) / self.wk
            if .1 < rel < .9 and y > self.w.ground - self.hk * .9:
                return self.dir * rng.uniform(100, 290) * u, -rng.uniform(80, 320) * u
        return None

    def draw_front(self, cr):
        moving = self.state in ("enter", "smash")
        step = int(self.t * 2.5) % 2 if moving else 0
        body, spikes = self.frames[step]
        bob = (1.5 * self.u) if moving and step else 0
        oy = self.w.ground - self.hk + bob
        cr.save()
        if self.dir > 0:
            cr.translate(self.x + self.wk, oy)
            cr.scale(-1, 1)
        else:
            cr.translate(self.x, oy)
        cr.set_source_rgb(*self.w.sil)
        cr.mask_surface(body, 0, 0)
        glow = self.state in ("roar", "breath")
        cr.set_source_rgb(*(BREATH if glow else self.w.sil))
        cr.mask_surface(spikes, 0, 0)
        cr.set_source_rgb(*EYE)
        cr.arc(.225 * self.wk, .15 * self.hk, 1.6 * self.u, 0, math.tau)
        cr.fill()
        cr.restore()
        if self.beam:
            x0, y0, x1, y1 = self.beam
            cr.set_line_cap(1)
            for col, wd, a in ((BREATH, 10, .35), (BREATH, 5, .9), (BREATH_CORE, 2, 1)):
                cr.set_source_rgba(*col, a)
                cr.set_line_width(wd * self.u * (1 + .15 * math.sin(self.t * 40)))
                cr.move_to(x0, y0)
                cr.line_to(x1, y1)
                cr.stroke()



# ---------------------------------------------------------------- shared helpers

def tapered(cr, pts, w0, w1):
    """Fill a limb along the polyline pts, its width going from w0 to w1."""
    n = len(pts)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        ax, ay = pts[max(0, i - 1)]
        bx, by = pts[min(n - 1, i + 1)]
        ln = math.hypot(bx - ax, by - ay) or 1
        nx, ny = -(by - ay) / ln, (bx - ax) / ln
        half = (w0 + (w1 - w0) * i / max(1, n - 1)) / 2
        left.append((x + nx * half, y + ny * half))
        right.append((x - nx * half, y - ny * half))
    cr.move_to(*left[0])
    for pt in left[1:] + right[::-1]:
        cr.line_to(*pt)
    cr.close_path()
    cr.fill()


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    ln2 = dx * dx + dy * dy or 1
    k = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / ln2))
    return math.hypot(px - (x0 + k * dx), py - (y0 + k * dy))


def blast_affect(blasts, x, y, rng, u):
    """Things inside a short-lived blast get thrown outwards."""
    for bx, by, r, _ in blasts:
        d = math.hypot(x - bx, y - by)
        if d < r:
            d = max(d, 1)
            return (x - bx) / d * rng.uniform(120, 260) * u, (y - by) / d * 160 * u - 100 * u
    return None


def clip_beam(w, x0, y0, x1, y1, bite):
    """A beam stops where it meets the first standing block, burning `bite` into it
    (so it eats its way through instead of passing through walls)."""
    hit = w.trace(x0, y0, x1, y1)
    if not hit:
        return x1, y1, False
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1
    return hit[0] + dx / ln * bite, hit[1] + dy / ln * bite, True


def scorch(w, x, y, u):
    """Sparks and smoke where a beam is burning into the stone."""
    if w.rng.random() < .5:
        w.smoke(x, y, w.rng.uniform(-15, 15) * u, -w.rng.uniform(15, 35) * u, w.rng.uniform(1.2, 2.5))
    w.spark(x, y, w.rng.uniform(-60, 60) * u, -w.rng.uniform(20, 90) * u, w.rng.uniform(.3, .8))


def age_blasts(blasts, dt):
    for b in blasts:
        b[3] -= dt
    return [b for b in blasts if b[3] > 0]


FIRE_GLOW = hexc("#ff7a1a")
HEAT_RAY = hexc("#ffcf6e")
SUCKER = (0.86, 0.66, 0.76)


# ---------------------------------------------------------------- dragon (myth)

class Dragon(Disaster):
    """A winged dragon flies in, breathes fire across the monument from one
    side, crosses over it, breathes again from the other side and flies off."""

    def __init__(self, w):
        super().__init__(w)
        u, rng = self.u, w.rng
        self.f = rng.choice((-1, 1))
        self.cx = (w.mx0 + w.mx1) / 2
        self.x = -160 * u if self.f > 0 else w.W + 160 * u
        self.base_y = max(95 * u, w.mtop - 45 * u)
        self.y = self.base_y
        self.origin_x = self.cx
        self.state, self.st = "approach", 0.0
        self.flap = 0.0
        self.fire = None
        self.breaths = 0

    def hover_x(self, f):
        return self.cx - f * ((self.w.mx1 - self.w.mx0) / 2 + 150 * self.u)

    def mouth(self):
        return self.x + self.f * 76 * self.u, self.y - 15 * self.u

    def update(self, dt):
        super().update(dt)
        w, u = self.w, self.u
        self.st += dt
        self.flap += dt * (2.2 if self.state != "breathe" else 1.4) * math.tau
        self.fire = None
        self.shake = 0
        if self.state == "approach":
            tx = self.hover_x(self.f)
            self.x += self.f * 170 * u * dt
            self.y = self.base_y + math.sin(self.t * 2) * 6 * u
            if (self.x - tx) * self.f >= 0:
                self.state, self.st = "breathe", 0.0
        elif self.state == "breathe":
            k = min(1.0, self.st / 3.4)
            self.y = self.base_y + math.sin(self.t * 1.5) * 4 * u
            mx, my = self.mouth()
            tx = self.cx - self.f * 20 * u
            ty = w.mtop + 10 * u + (w.ground - 40 * u - w.mtop) * k
            dx, dy = tx - mx, ty - my
            ln = math.hypot(dx, dy) or 1
            ex, ey, hit = clip_beam(w, mx, my, mx + dx / ln * (ln + 70 * u), my + dy / ln * (ln + 70 * u), 8 * u)
            if hit:
                scorch(w, ex, ey, u)
            self.fire = (mx, my, dx / ln, dy / ln, math.hypot(ex - mx, ey - my))
            self.shake = 1.5 * u
            if self.st > 1 and w.rng.random() < .4:
                w.smoke(tx, ty, w.rng.uniform(-20, 20) * u, -25 * u, w.rng.uniform(1.5, 3))
            if self.st > 3.4:
                self.breaths += 1
                self.state, self.st = ("cross", 0.0) if self.breaths < 2 else ("leave", 0.0)
                self.from_x = self.x
        elif self.state == "cross":
            to = self.hover_x(-self.f)
            k = min(1.0, self.st / 2.6)
            self.x = self.from_x + (to - self.from_x) * (k * k * (3 - 2 * k))
            self.y = self.base_y - math.sin(k * math.pi) * 70 * u
            if k >= 1:
                self.f = -self.f
                self.state, self.st = "breathe", 0.0
        else:  # leave
            self.x += self.f * 210 * u * dt
            self.y -= 70 * u * dt
            if self.x < -220 * u or self.x > w.W + 220 * u:
                self.done = True

    def affect(self, x, y):
        if not self.fire:
            return None
        mx, my, dx, dy, length = self.fire
        vx, vy = x - mx, y - my
        along = vx * dx + vy * dy
        if 0 < along < length and abs(vx * dy - vy * dx) < along * .2 + 4 * self.u:
            rng, u = self.w.rng, self.u
            return dx * rng.uniform(160, 300) * u, dy * 120 * u - rng.uniform(80, 180) * u
        return None

    def wing(self, cr, sx, sy, f, s):
        u = self.u
        elbow = (sx - f * 14 * u, sy - 38 * u * s - 6 * u)
        t1 = (sx - f * 56 * u, sy - 54 * u * s + 4 * u)
        t2 = (sx - f * 74 * u, sy - 26 * u * s + 12 * u)
        t3 = (sx - f * 54 * u, sy + 6 * u + 6 * u * s)
        root = (sx - f * 30 * u, sy + 4 * u)
        cr.move_to(sx, sy)
        cr.line_to(*elbow)
        cr.line_to(*t1)
        for a, b in ((t1, t2), (t2, t3), (t3, root)):  # scalloped trailing edge
            mx, my = (a[0] + b[0]) / 2 + f * 6 * u, (a[1] + b[1]) / 2 + 4 * u
            cr.curve_to(mx, my, mx, my, *b)
        cr.close_path()
        cr.fill()

    def draw_front(self, cr):
        u, x, y, f = self.u, self.x, self.y, self.f
        s = math.sin(self.flap)
        if self.fire:
            mx, my, dx, dy, length = self.fire
            px, py = -dy, dx
            for jitter, alpha in ((.05, .55), (-.03, .9)):
                spread = (.2 + jitter * math.sin(self.t * 23)) * length
                ex, ey = mx + dx * length, my + dy * length
                grad = cairo.LinearGradient(mx, my, ex, ey)
                grad.add_color_stop_rgba(0, *FIRE1, alpha)
                grad.add_color_stop_rgba(.25, *FIRE2, alpha * .9)
                grad.add_color_stop_rgba(.7, *FIRE_GLOW, alpha * .6)
                grad.add_color_stop_rgba(1, *FIRE3, 0)
                cr.move_to(mx, my)
                cr.line_to(ex + px * spread, ey + py * spread)
                cr.line_to(ex - px * spread, ey - py * spread)
                cr.close_path()
                cr.set_source(grad)
                cr.fill()
        cr.set_source_rgb(*self.w.sil)
        self.wing(cr, x - f * 6 * u, y - 10 * u, f, math.sin(self.flap + .5))  # far wing
        tail = [(x - f * (26 * u + 72 * u * k), y + 3 * u + 10 * u * k + 8 * u * math.sin(k * 4 + self.t * 3))
                for k in (i / 10 for i in range(11))]
        tapered(cr, tail, 10 * u, 1.5 * u)
        ex, ey = tail[-1]
        cr.move_to(ex, ey - 5 * u)
        cr.line_to(ex - f * 9 * u, ey)
        cr.line_to(ex, ey + 5 * u)
        cr.close_path()
        cr.fill()
        cr.save()
        cr.translate(x, y)
        cr.scale(30 * u, 10 * u)
        cr.arc(0, 0, 1, 0, math.tau)
        cr.restore()
        cr.fill()
        tapered(cr, [(x + f * 20 * u, y - 3 * u), (x + f * 40 * u, y - 14 * u), (x + f * 56 * u, y - 17 * u)], 12 * u, 6 * u)
        cr.save()
        cr.translate(x + f * 62 * u, y - 17 * u)
        cr.scale(9 * u, 5 * u)
        cr.arc(0, 0, 1, 0, math.tau)
        cr.restore()
        cr.fill()
        jaw = 5 * u if self.fire else 0
        cr.move_to(x + f * 66 * u, y - 21 * u)
        cr.line_to(x + f * 77 * u, y - 16 * u)
        cr.line_to(x + f * 66 * u, y - 13 * u)
        cr.close_path()
        cr.move_to(x + f * 64 * u, y - 14 * u)
        cr.line_to(x + f * 74 * u, y - 12 * u + jaw)
        cr.line_to(x + f * 62 * u, y - 11 * u)
        cr.close_path()
        for hx in (56, 60):  # horns
            cr.move_to(x + f * (hx + 2) * u, y - 21 * u)
            cr.line_to(x + f * (hx - 8) * u, y - 31 * u)
            cr.line_to(x + f * (hx + 5) * u, y - 20 * u)
            cr.close_path()
        cr.fill()
        for lx, ly, tx, ty in ((14, 6, 18, 20), (-14, 6, -20, 20)):
            tapered(cr, [(x + f * lx * u, y + ly * u), (x + f * tx * u, y + ty * u)], 6 * u, 3 * u)
        self.wing(cr, x + f * 6 * u, y - 8 * u, f, s)
        cr.set_source_rgb(*FIRE2)
        cr.arc(x + f * 63 * u, y - 19 * u, 1.3 * u, 0, math.tau)
        cr.fill()


# ---------------------------------------------------------------- kraken (myth)

class Kraken(Disaster):
    """Tentacles burst up through the ground, sway, slam across the monument
    and pull back down."""

    RISE, SLAM, RETREAT, END = 1.8, 6.0, 9.5, 12.0

    def __init__(self, w):
        super().__init__(w)
        u, rng = self.u, w.rng
        self.cx = (w.mx0 + w.mx1) / 2
        self.origin_x = self.cx
        reach = max(230 * u, (w.ground - w.mtop) * 1.15)
        n = rng.randint(5, 7)
        x0, x1 = w.mx0 - 90 * u, w.mx1 + 90 * u
        self.tent = []
        for i in range(n):
            bx = x0 + (x1 - x0) * (i + rng.uniform(.2, .8)) / n
            self.tent.append({"x": bx, "len": reach * rng.uniform(.8, 1.15), "ph": rng.uniform(0, 6),
                              "dir": 1 if bx < self.cx else -1, "w": rng.uniform(18, 26) * u,
                              "far": abs(self.cx - bx) + 140 * u})
        self.burst = False

    def growth(self):
        t = self.t
        if t < self.RISE:
            return 0.0
        if t < self.RISE + 2.2:
            k = (t - self.RISE) / 2.2
            return k * k * (3 - 2 * k)
        if t < self.RETREAT:
            return 1.0
        return max(0.0, 1 - (t - self.RETREAT) / 2)

    def lean(self):
        if self.t < self.SLAM:
            return 0.0
        k = min(1.0, (self.t - self.SLAM) / 1.3)
        return k * k * (3 - 2 * k)

    def centerline(self, tn):
        u, g, lean = self.u, self.growth(), self.lean()
        length = tn["len"] * g
        pts = []
        for i in range(17):
            s = i / 16
            sway = math.sin(s * 3.2 + self.t * 1.6 + tn["ph"]) * 24 * u * s * (1 - lean)
            curl = -tn["dir"] * 34 * u * max(0.0, (s - .7) / .3) ** 2 * (1 - lean)
            x = tn["x"] + sway + curl + tn["dir"] * lean * s * s * tn["far"]
            y = self.w.ground - s * length * (1 - .55 * lean * s)
            pts.append((x, y))
        return pts

    def update(self, dt):
        super().update(dt)
        w, u, t = self.w, self.u, self.t
        self.shake = (3 if t < self.RISE + .5 else 0) * u
        if self.SLAM < t < self.SLAM + 1.5:
            self.shake = 7 * u
        if t >= self.RISE and not self.burst:
            self.burst = True
            for tn in self.tent:
                for _ in range(6):
                    w.smoke(tn["x"], w.ground - 2 * u, w.rng.uniform(-40, 40) * u, -w.rng.uniform(20, 60) * u, 2.5)
        if t > self.END:
            self.done = True

    def affect(self, x, y):
        if self.growth() < .15:
            return None
        rng, u, slamming = self.w.rng, self.u, self.t >= self.SLAM
        for tn in self.tent:
            pts = self.centerline(tn)
            for i in range(len(pts) - 1):
                wdt = tn["w"] * (1 - i / 16) / 2 + 3 * u
                if seg_dist(x, y, *pts[i], *pts[i + 1]) < wdt:
                    if slamming:
                        return tn["dir"] * rng.uniform(150, 290) * u, rng.uniform(-60, 80) * u
                    return rng.uniform(-70, 70) * u, -rng.uniform(80, 200) * u
        return None

    def draw_front(self, cr):
        u, g = self.u, self.w.ground
        if self.growth() <= 0:
            return
        for tn in self.tent:
            pts = self.centerline(tn)
            cr.set_source_rgb(*self.w.sil)
            tapered(cr, pts, tn["w"], 2.5 * u)
            cr.set_source_rgba(*SUCKER, .4)
            for i in range(2, 15, 2):
                (ax, ay), (bx, by) = pts[i - 1], pts[i + 1]
                ln = math.hypot(bx - ax, by - ay) or 1
                nx, ny = -(by - ay) / ln * tn["dir"], (bx - ax) / ln * tn["dir"]
                wdt = tn["w"] * (1 - i / 16)
                cx, cy = pts[i]
                cr.arc(cx + nx * wdt * .3, cy + ny * wdt * .3, max(1.0, wdt * .13), 0, math.tau)
                cr.fill()
            cr.set_source_rgb(*self.w.sil)  # broken ground around the base
            cr.save()
            cr.translate(tn["x"], g)
            cr.scale(tn["w"] * 1.5, 7 * u)
            cr.arc(0, 0, 1, math.pi, 0)
            cr.restore()
            cr.fill()


# ---------------------------------------------------------------- Martian tripods (H. G. Wells, 1898)

class Tripods(Disaster):
    """Two three-legged fighting machines stride in from either side, sweep
    their heat-rays across the monument, then march on through."""

    def __init__(self, w):
        super().__init__(w)
        u = self.u
        self.cx = (w.mx0 + w.mx1) / 2
        self.origin_x = self.cx
        self.height = min(w.ground - 40 * u, max(300 * u, (w.ground - w.mtop) * .95))
        self.blasts = []
        self.machines = []
        for d, delay in ((1, 0.0), (-1, 1.6)):
            x = -110 * u if d > 0 else w.W + 110 * u
            stop = (w.mx0 - 150 * u) if d > 0 else (w.mx1 + 150 * u)
            self.machines.append({"x": x, "d": d, "stop": stop, "delay": delay, "state": "walk", "st": 0.0,
                                  "feet": [{"x": x + k * 34 * u, "from": 0.0, "k": -1.0} for k in (-1, 0, 1)],
                                  "ray": None})

    def body_y(self, m):
        return self.w.ground - self.height + math.sin(self.t * 3 + m["d"]) * 3 * self.u

    def projector(self, m):
        u = self.u
        return m["x"] + m["d"] * 50 * u, self.body_y(m) + 12 * u

    def step_feet(self, m, dt, speed):
        u = self.u
        stride = 70 * u
        moving = [ft for ft in m["feet"] if ft["k"] >= 0]
        for ft in moving:
            ft["k"] += dt / .32
            if ft["k"] >= 1:
                ft["k"] = -1.0
                ft["x"] = ft["to"]
                self.blasts.append([ft["x"], self.w.ground - 6 * u, 18 * u, .12])  # the foot comes down
        if not moving and speed:
            behind = min(m["feet"], key=lambda ft: ft["x"] * m["d"])
            if (m["x"] - behind["x"]) * m["d"] > stride * .45:
                behind["from"], behind["to"], behind["k"] = behind["x"], m["x"] + m["d"] * stride * .55, 0.0

    def update(self, dt):
        super().update(dt)
        w, u = self.w, self.u
        self.shake = 0
        self.blasts = age_blasts(self.blasts, dt)
        gone = 0
        for m in self.machines:
            if self.t < m["delay"]:
                continue
            m["st"] += dt
            m["ray"] = None
            speed = 0.0
            if m["state"] == "walk":
                speed = 75 * u
                if (m["x"] - m["stop"]) * m["d"] >= 0:
                    m["state"], m["st"] = "ray", 0.0
            elif m["state"] == "ray":
                k = min(1.0, m["st"] / 3.6)
                px, py = self.projector(m)
                tx = self.cx + m["d"] * (w.mx1 - w.mx0) * (.25 - .5 * k)
                ty = w.mtop + 6 * u + (w.ground - 30 * u - w.mtop) * (.5 - .5 * math.cos(k * math.pi * 2))
                ln = math.hypot(tx - px, ty - py) or 1
                ex, ey = tx + (tx - px) / ln * 120 * u, ty + (ty - py) / ln * 120 * u  # on until it hits
                ex, ey, hit = clip_beam(w, px, py, ex, ey, 6 * u)
                if hit:
                    scorch(w, ex, ey, u)
                m["ray"] = (px, py, ex, ey)
                self.shake = 1.2 * u
                if m["st"] > 3.6:
                    m["state"] = "march"
            else:
                speed = 105 * u
                if m["x"] < -200 * u or m["x"] > w.W + 200 * u:
                    gone += 1
            m["x"] += m["d"] * speed * dt
            self.step_feet(m, dt, speed)
            for ft in m["feet"]:
                if ft["k"] >= 0 and ft["k"] > .9:
                    self.shake = max(self.shake, 2.5 * u)
        if gone == len(self.machines):
            self.done = True

    def affect(self, x, y):
        rng, u = self.w.rng, self.u
        hit = blast_affect(self.blasts, x, y, rng, u)
        if hit:
            return hit
        for m in self.machines:
            if m["ray"] and seg_dist(x, y, *m["ray"]) < 8 * u:
                px, py, tx, ty = m["ray"]
                ln = math.hypot(tx - px, ty - py) or 1
                return (tx - px) / ln * rng.uniform(120, 240) * u, -rng.uniform(80, 200) * u
        return None

    def draw_front(self, cr):
        u, g = self.u, self.w.ground
        for m in self.machines:
            if self.t < m["delay"]:
                continue
            by = self.body_y(m)
            if m["ray"]:
                px, py, tx, ty = m["ray"]
                cr.set_line_cap(1)
                for col, wd, a in ((HEAT_RAY, 12, .3), (HEAT_RAY, 6, .8), (FIRE1, 2, 1)):
                    cr.set_source_rgba(*col, a)
                    cr.set_line_width(wd * u)
                    cr.move_to(px, py)
                    cr.line_to(tx, ty)
                    cr.stroke()
            cr.set_source_rgb(*self.w.sil)
            for i, ft in enumerate(m["feet"]):
                fx = ft["x"] if ft["k"] < 0 else ft["from"] + (ft["to"] - ft["from"]) * ft["k"]
                fy = g - (math.sin(math.pi * ft["k"]) * 30 * u if ft["k"] >= 0 else 0)
                hx, hy = m["x"] + (i - 1) * 14 * u, by + 14 * u
                kx = (hx + fx) / 2 + (i - 1) * 26 * u
                ky = (hy + fy) / 2 - (fy - hy) * .12
                cr.set_line_width(4 * u)
                cr.move_to(hx, hy)
                cr.line_to(kx, ky)
                cr.line_to(fx, fy)
                cr.stroke()
                cr.arc(fx, fy - 2 * u, 4 * u, 0, math.tau)
                cr.fill()
            for k in (-1, 1):  # dangling metal tentacles
                cr.set_line_width(1.6 * u)
                sx = m["x"] + k * 10 * u
                cr.move_to(sx, by + 12 * u)
                cr.curve_to(sx + k * 8 * u, by + 40 * u, sx + math.sin(self.t * 2 + k) * 16 * u, by + 60 * u,
                            sx + math.sin(self.t * 2.5 + k) * 10 * u, by + 78 * u)
                cr.stroke()
            cr.save()
            cr.translate(m["x"], by)
            cr.scale(38 * u, 14 * u)
            cr.arc(0, 0, 1, 0, math.tau)
            cr.restore()
            cr.fill()
            cr.save()
            cr.translate(m["x"] - m["d"] * 4 * u, by - 8 * u)
            cr.scale(24 * u, 16 * u)
            cr.arc(0, 0, 1, math.pi, 0)
            cr.restore()
            cr.fill()
            px, py = self.projector(m)
            tapered(cr, [(m["x"] + m["d"] * 30 * u, by + 2 * u), (px, py)], 5 * u, 3 * u)
            cr.rectangle(px - 4 * u, py - 3 * u, 8 * u, 6 * u)
            cr.fill()
            cr.set_source_rgba(*HEAT_RAY, .9 if m["ray"] else .5)
            cr.arc(px + m["d"] * 4 * u, py, 2 * u, 0, math.tau)
            cr.fill()


# ---------------------------------------------------------------- giant ape

class GiantApe(Disaster):
    """A giant ape knuckle-walks in and climbs the monument. On a low building it
    hauls itself up onto the roof, beats its chest and pounds its way down through
    it; on a tall one it clings near the top, beats its chest with its free fist
    and punches chunks out of the wall as it climbs down. Hands and feet always
    rest on blocks that are still standing: knock them away and it drops."""

    GRAVITY = 600

    def __init__(self, w):
        super().__init__(w)
        u, rng = self.u, w.rng
        self.h = max(120 * u, min(190 * u, (w.ground - w.mtop) * .42))
        self.mount = w.ground - w.mtop < 1.35 * self.h   # low enough to stand on top of
        self.f = rng.choice((-1, 1))              # faces the monument
        self.x = -90 * u if self.f > 0 else w.W + 90 * u
        self.y = w.ground
        self.origin_x = (w.mx0 + w.mx1) / 2
        self.state, self.st = "walk", 0.0
        self.ph = 0.0
        self.blasts = []
        self.strikes = 0
        self.vx = self.vy = 0.0
        self.skel = None
        self.pose_walk()

    # ---- what it can hold on to and stand on ----
    def face(self, y):
        """The monument's outer face on the ape's side at height y (only what still stands)."""
        span = self.w.solid_span(y)
        if not span:
            return None
        return span[0] if self.f > 0 else span[1]

    def grab(self, y):
        """Where a hand reaching for height y can hold on: the wall there, or the top
        edge just below if it reaches over the top. None: nothing within reach."""
        for k in range(14):
            yy = y + k * .04 * self.h
            if yy >= self.w.ground:
                break
            e = self.face(yy)
            if e is not None and abs(e - (self.x + self.f * .24 * self.h)) < .3 * self.h:
                return e, yy
        return None

    def support(self, x):
        """Height a foot at x comes to rest on: standing blocks, rubble or the ground."""
        w = self.w
        best = w.ground - w.hm[min(w.W, max(0, int(x)))]
        for dx in (-.03, 0, .03):
            top = w.solid_top(x + dx * self.h)
            if top is not None:
                best = min(best, top)
        return best

    def feet_x(self):
        return self.x + self.f * .1 * self.h, self.x - self.f * .05 * self.h

    def stand_y(self):
        return min(self.support(fx) for fx in self.feet_x())

    # ---- update ----
    def update(self, dt):
        super().update(dt)
        w, u, h = self.w, self.u, self.h
        self.st += dt
        self.shake = 0
        self.blasts = age_blasts(self.blasts, dt)
        st = self.state
        if st == "walk":
            self.ph += dt * 7
            self.x += self.f * 115 * u * dt
            wall = self.face(w.ground - 4 * u)
            if wall is None and (self.x - self.origin_x) * self.f > 0:
                self.state = "leave"  # nothing left to climb
            elif wall is not None and (self.x + self.f * .3 * h - wall) * self.f >= 0:
                # a sheer wall gets climbed; a slope or terraces get scrambled up on foot
                mid = self.face(w.ground - .5 * h)
                if mid is None or (mid - wall) * self.f > .3 * h:
                    self.state, self.st, self.mount = "scramble", 0.0, True
                else:
                    self.state, self.st = "climb", 0.0
            self.pose_walk()
        elif st == "scramble":  # up the slope, hands on the stones ahead
            self.ph += dt * 6
            # the summit: nothing higher than where it stands anywhere close ahead
            ahead = min(self.support(self.x + self.f * k * .1 * h) for k in range(3, 13))
            if ahead > self.y - .02 * h or self.st > 14:
                self.state, self.st = "beat", 0.0
            else:
                self.x += self.f * 50 * u * dt
                target = self.stand_y()
                self.y = target if target > self.y else max(target, self.y - 120 * u * dt)
            self.pose_stand(crouch=.6)
        elif st == "climb":
            self.ph += dt * 6
            self.y = max(w.mtop, self.y - 90 * u * dt)
            chest = self.grab(self.y - .55 * h)
            if chest:
                self.x += (chest[0] - self.f * .24 * h - self.x) * min(1.0, dt * 8)
            low = self.face(self.y - .3 * h)
            roof = w.solid_top(self.x + self.f * .32 * h)  # top of the wall just ahead
            no_grip = self.grab(self.y - .98 * h) is None and self.grab(self.y - .86 * h) is None
            over = roof is not None and roof >= self.y - .6 * h
            if over and (self.mount or no_grip or roof - w.mtop < .6 * h):
                self.mount = True
            if self.mount:
                # over the edge: the top of the wall is below its chest, or the wall
                # at hip height is gone or steps back into a roof
                at_feet = self.face(self.y - .05 * h)
                if over or low is None or (at_feet is not None and (low - at_feet) * self.f > .2 * h) or self.st > 9:
                    self.state, self.st = "mantle", 0.0
                    self.from_xy = (self.x, self.y)
                    roof = max(w.mx0 + .15 * h, min(w.mx1 - .15 * h, self.x + self.f * .32 * h))
                    self.x = roof
                    self.to_xy = (roof, self.stand_y())
                    self.x = self.from_xy[0]
            elif self.grab(self.y - 1.05 * h) is None or self.y - 1.0 * h <= w.mtop or self.st > 9:
                self.state, self.st = "beat", 0.0
            if self.state == "climb" and not self.pose_climb():
                self.fall()
        elif st == "mantle":  # haul itself up over the edge onto the roof
            k = min(1.0, self.st / 1.1)
            e = k * k * (3 - 2 * k)
            (x0, y0), (x1, y1) = self.from_xy, self.to_xy
            self.x = x0 + (x1 - x0) * e
            self.y = y0 + (y1 - y0) * e - math.sin(k * math.pi) * .12 * h
            self.pose_stand(crouch=1 - k)
            if k >= 1:
                self.state, self.st = "beat", 0.0
        elif st == "beat":
            self.ph += dt * 14
            self.shake = 2 * u
            if self.mount:
                self.settle(dt)
                self.pose_stand()
            elif not self.pose_climb(beat=True):
                self.fall()
            if self.st > 2.2 and self.state == "beat":
                self.state, self.st = "smash", 0.0
        elif st == "smash":
            k = self.st % .9
            hit = k >= .45 and self.st // .9 == self.strikes
            if self.mount:
                self.settle(dt)
                if hit:  # both fists down on the roof in front of it
                    fx = self.x + self.f * .32 * h
                    fy = self.support(fx)
                    self.impact(fx, fy + .04 * h, .32 * h)
                    self.impact(fx + self.f * .22 * h, fy + .14 * h, .26 * h)
                self.pose_stand(fists=k)
                if hit:
                    self.x += self.f * .06 * h  # step forward into the damage
            else:
                if hit:  # the free fist punches into the wall beside it
                    py = self.y - .5 * h
                    wall = self.face(py)
                    if wall is not None:
                        self.impact(wall + self.f * .04 * h, py, .3 * h)
                        self.impact(wall + self.f * .3 * h, py + .1 * h, .24 * h)
                if k > .5:  # then climbs down a little, hand over hand
                    self.y = min(w.ground, self.y + .55 * h * dt / .4)
                    self.ph += dt * 6
                    chest = self.grab(self.y - .55 * h)
                    if chest:
                        self.x += (chest[0] - self.f * .24 * h - self.x) * min(1.0, dt * 8)
                if not self.pose_climb(punch=k):
                    self.fall()
            if hit:
                self.strikes += 1
                self.shake = 7 * u
            if self.strikes >= 4 and k > .75 and self.state == "smash":
                self.state, self.st = "jump", 0.0
                self.vx, self.vy = -self.f * (90 if self.mount else 40) * u, (-170 if self.mount else 0) * u
        elif st in ("jump", "fall"):
            self.vy += self.GRAVITY * u * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            target = self.stand_y()
            if self.vy > 0 and self.y >= target:
                self.y = target
                self.shake = 5 * u
                if st == "jump" or target >= w.ground - 2 * u:
                    self.f = -self.f
                    self.state, self.st = "leave", 0.0
                else:  # landed on what is left of the roof: carry on smashing from there
                    self.mount = True
                    self.state, self.st = "smash", self.strikes * .9
            self.pose_stand(air=True)
        else:  # leave
            self.ph += dt * 8
            self.x += self.f * 140 * u * dt
            self.y = w.ground
            self.pose_walk()
            if self.x < -200 * u or self.x > w.W + 200 * u:
                self.done = True

    def fall(self):
        """Lost its grip (the blocks it held went): drop."""
        self.state, self.st = "fall", 0.0
        self.vx, self.vy = -self.f * 20 * self.u, 0.0

    def settle(self, dt):
        """Standing on the roof: drop into any hole knocked out under its feet."""
        target = self.stand_y()
        if self.y < target - 1:
            self.vy += self.GRAVITY * self.u * dt
            self.y = min(target, self.y + self.vy * dt)
        else:
            self.y, self.vy = target, 0.0

    def impact(self, x, y, r):
        self.blasts.append([x, y, r, .15])
        for _ in range(6):
            self.w.smoke(x, y, self.w.rng.uniform(-40, 40) * self.u, -self.w.rng.uniform(10, 50) * self.u, 2)

    # ---- skeleton: hip, shoulder, head, hands, feet ----
    def upright(self):
        x, y, f, h = self.x, self.y, self.f, self.h
        return (x, y - .38 * h), (x + f * .05 * h, y - .74 * h), (x + f * .11 * h, y - .87 * h)

    def pose_walk(self):
        x, y, f, h, ph = self.x, self.y, self.f, self.h, self.ph
        self.skel = ((x - f * .1 * h, y - .4 * h), (x + f * .16 * h, y - .62 * h), (x + f * .3 * h, y - .66 * h),
                     [(x + f * (.3 + .08 * math.sin(ph)) * h, y), (x + f * (.3 - .08 * math.sin(ph)) * h, y)],
                     [(x - f * (.12 + .06 * math.sin(ph)) * h, y), (x - f * (.12 - .06 * math.sin(ph)) * h, y)])

    def pose_climb(self, beat=False, punch=None):
        """Hands and feet on the wall. False if there's nothing left to hold."""
        h, f, y, ph = self.h, self.f, self.y, self.ph
        hip, shoulder, head = self.upright()
        a = math.sin(ph)
        hands = [self.grab(y - (.98 + .08 * a) * h), self.grab(y - (.86 - .08 * a) * h)]
        if beat or punch is not None:
            hands[1] = self.grab(y - 1.0 * h)
        if hands[0] is None and hands[1] is None:
            return False
        hands = [hd or hands[1 - i] for i, hd in enumerate(hands)]
        if beat:  # one hand holds on, the other beats its chest
            hands[0] = (shoulder[0] + f * .1 * h, shoulder[1] + (.08 + .04 * a) * h)
        elif punch is not None:
            if punch < .45:  # wind up
                hands[0] = (shoulder[0] - f * .06 * h, shoulder[1] - .12 * h * punch / .45)
            elif punch < .6:
                wall = self.face(y - .5 * h)
                hands[0] = (wall if wall is not None else shoulder[0] + f * .3 * h, y - .5 * h)
            else:
                hands[0] = self.grab(y - .9 * h) or hands[1]
        feet = []
        for k, fy in enumerate((y - (.06 + .05 * a) * h, y - (.02 - .05 * a) * h)):
            if fy >= self.w.ground - 2:
                feet.append((self.x + f * (.1 - .05 * k) * h, self.w.ground))
                continue
            for j in range(6):  # brace against the wall here, or a little lower down
                yy = fy + j * .04 * h
                e = self.face(yy)
                if e is not None and abs(e - (self.x + f * .2 * h)) < .3 * h:
                    feet.append((e, yy))
                    break
            else:  # nothing in reach under this foot: it hangs
                feet.append((self.x + f * (.12 - .05 * k) * h, y + .02 * h))
        self.skel = (hip, shoulder, head, hands, feet)
        return True

    def pose_stand(self, fists=None, crouch=0.0, air=False):
        x, y, f, h = self.x, self.y, self.f, self.h
        hip, shoulder, head = self.upright()
        if crouch:
            dy = crouch * .2 * h
            hip, shoulder, head = (hip[0], hip[1] + dy * .5), (shoulder[0] + f * .1 * h * crouch, shoulder[1] + dy), \
                (head[0] + f * .12 * h * crouch, head[1] + dy)
        feet = []
        for fx in self.feet_x():
            sy = y if air else self.support(fx)
            feet.append((fx, y if sy - y > .15 * h else sy))  # a foot over a hole just hangs
        a = math.sin(self.ph)
        if air:
            hands = [(x - f * .2 * h, y - 1.05 * h), (x + f * .25 * h, y - 1.0 * h)]
        elif crouch:  # pulling itself up: hands flat on the roof ahead
            hands = [(x + f * .3 * h, self.support(x + f * .3 * h)), (x + f * .22 * h, self.support(x + f * .22 * h))]
        elif fists is None:  # beating its chest
            hands = [(x + f * .18 * h, y - (.64 + .05 * a) * h), (x + f * .13 * h, y - (.6 - .05 * a) * h)]
        elif fists < .45:  # fists raised
            lift = fists / .45
            hands = [(x + f * (.05 + .1 * lift) * h, y - (.8 + .4 * lift) * h)] * 2
        else:  # fists down on the roof
            fx = x + f * .32 * h
            fy = min(self.support(fx), y + .1 * h)
            hands = [(fx, fy), (fx - f * .05 * h, fy)]
        self.skel = (hip, shoulder, head, hands, feet)

    def affect(self, x, y):
        return blast_affect(self.blasts, x, y, self.w.rng, self.u)

    def draw_front(self, cr):
        h, f = self.h, self.f
        hip, shoulder, head, hands, feet = self.skel
        cr.set_source_rgb(*self.w.sil)
        for fx, fy in feet:  # legs
            kx, ky = (hip[0] + fx) / 2 + f * .06 * h, (hip[1] + fy) / 2
            tapered(cr, [hip, (kx, ky), (fx, fy)], .15 * h, .1 * h)
        tapered(cr, [hip, ((hip[0] + shoulder[0]) / 2, (hip[1] + shoulder[1]) / 2), shoulder], .34 * h, .42 * h)
        cr.arc(shoulder[0] - f * .04 * h, shoulder[1] + .02 * h, .17 * h, 0, math.tau)  # shoulder hump
        cr.fill()
        cr.arc(head[0], head[1], .085 * h, 0, math.tau)
        cr.fill()
        cr.save()
        cr.translate(head[0] + f * .06 * h, head[1] + .03 * h)
        cr.scale(.06 * h, .045 * h)
        cr.arc(0, 0, 1, 0, math.tau)  # muzzle
        cr.restore()
        cr.fill()
        cr.rectangle(min(head[0], head[0] + f * .1 * h), head[1] - .045 * h, .1 * h, .03 * h)  # brow
        cr.fill()
        for hx, hy in hands:  # arms
            sx, sy = shoulder
            ex, ey = (sx + hx) / 2 - f * .07 * h, (sy + hy) / 2 + .05 * h
            tapered(cr, [(sx, sy), (ex, ey), (hx, hy)], .13 * h, .09 * h)
            cr.arc(hx, hy, .055 * h, 0, math.tau)
            cr.fill()


# ---------------------------------------------------------------- UFO

class UFO(Disaster):
    def __init__(self, w):
        super().__init__(w)
        u = self.u
        side = w.rng.choice((-1, 1))
        self.start = (w.W / 2 + side * (w.W / 2 + 80 * u), 50 * u)
        self.hover = ((w.mx0 + w.mx1) / 2, max(45 * u, w.mtop - 80 * u))
        self.ux, self.uy = self.start
        self.origin_x = self.hover[0]
        self.beam_on = False

    def update(self, dt):
        super().update(dt)
        t, u = self.t, self.u
        sx, sy = self.start
        hx, hy = self.hover
        self.beam_on = 3.8 < t < 10
        if t < 3:
            k = 1 - (1 - t / 3) ** 3
            self.ux, self.uy = sx + (hx - sx) * k, sy + (hy - sy) * k + math.sin(t * 4) * 5 * u
        elif t < 10.5:
            self.ux, self.uy = hx + math.sin(t * 1.3) * 8 * u, hy + math.sin(t * 2.1) * 4 * u
        else:
            k = (t - 10.5) / 1.6
            self.ux, self.uy = hx + (sx - hx) * k * k, hy - 320 * u * k * k
            if k >= 1:
                self.done = True

    def halfw(self, y):
        return 10 * self.u + (y - self.uy) * .24

    def affect(self, x, y):
        if self.beam_on and y > self.uy and abs(x - self.ux) <= self.halfw(y):
            return ABDUCT
        return None

    def force(self, p, dt):
        if p.abduct:
            p.vx = (self.ux - p.x) * 1.2
            p.vy = -(95 + p.life * 8) * self.u
            p.life += dt
            if p.y <= self.uy + 8 * self.u:
                p.dead = True

    def draw_back(self, cr):
        if self.beam_on:
            g = self.w.ground
            top = self.uy + 8 * self.u
            hw0, hw1 = self.halfw(top), self.halfw(g)
            grad = cairo.LinearGradient(0, top, 0, g)
            a = .3 + .05 * math.sin(self.t * 9)
            grad.add_color_stop_rgba(0, *BEAM, a + .15)
            grad.add_color_stop_rgba(1, *BEAM, a * .5)
            cr.move_to(self.ux - hw0, top)
            cr.line_to(self.ux + hw0, top)
            cr.line_to(self.ux + hw1, g)
            cr.line_to(self.ux - hw1, g)
            cr.close_path()
            cr.set_source(grad)
            cr.fill()

    def draw_front(self, cr):
        u, x, y = self.u, self.ux, self.uy
        cr.set_source_rgba(*BEAM, .55)
        cr.save()
        cr.translate(x, y - 4 * u)
        cr.scale(10 * u, 8 * u)
        cr.arc(0, 0, 1, math.pi, 0)
        cr.restore()
        cr.fill()
        cr.set_source_rgb(*self.w.sil)
        cr.save()
        cr.translate(x, y)
        cr.scale(30 * u, 7 * u)
        cr.arc(0, 0, 1, 0, math.tau)
        cr.restore()
        cr.fill()
        cr.set_source_rgb(*UFO_LIGHT)
        for i in range(7):
            if (i + int(self.t * 6)) % 3 == 0:
                cr.arc(x - 21 * u + i * 7 * u, y + 1 * u, 1.6 * u, 0, math.tau)
                cr.fill()


# ---------------------------------------------------------------- space battle

LASER, LASER_CORE = hexc("#c46bff"), hexc("#f6e9ff")
STATION_HI, STATION_LO = hexc("#a7acb8"), hexc("#474b57")
ENGINE = hexc("#ffb054")


class SpaceBattle(Disaster):
    """A ringed fortress-planet looms; delta fighters strafe the monument; then
    the fortress fires its main beam."""

    ARRIVE, STRAFE_END, CHARGE, FIRE, LEAVE = 3.0, 9.0, 11.0, 12.4, 15.5

    def __init__(self, w):
        super().__init__(w)
        u, rng = self.u, w.rng
        self.side = rng.choice((-1, 1))
        self.R = 52 * u
        self.sx = w.W / 2 + self.side * w.W * .3
        self.sy = max(self.R + 20 * u, w.mtop - 110 * u)
        self.target = ((w.mx0 + w.mx1) / 2, w.mtop + (w.ground - w.mtop) * .45)
        self.origin_x = self.target[0]
        self.fighters = []
        self.bolts = []
        self.blasts = []      # (x, y, radius, ttl) - knocks things for a moment
        self.ring = -1
        self.impacted = False
        self.next_wave = 1.2
        self.alpha = 0.0
        self.aimed = False

    def dish(self):
        """The emitter under the fortress, where the main beam leaves from."""
        return self.sx, self.sy + 1.05 * self.R

    def launch_wave(self):
        w, u, rng = self.w, self.u, self.w.rng
        d = rng.choice((-1, 1))
        y = rng.uniform(max(30 * u, w.mtop - 80 * u), w.mtop + (w.ground - w.mtop) * .4)
        for k in range(rng.randint(2, 3)):
            self.fighters.append({"x": -60 * u - k * 40 * u if d > 0 else w.W + 60 * u + k * 40 * u,
                                  "y": y + k * 18 * u, "d": d, "fire": rng.uniform(.1, .4),
                                  "v": rng.uniform(240, 300) * u, "bob": rng.uniform(0, 6)})

    def update(self, dt):
        super().update(dt)
        t, u, w, rng = self.t, self.u, self.w, self.w.rng
        self.alpha = min(1.0, t / self.ARRIVE) if t < self.LEAVE else max(0.0, 1 - (t - self.LEAVE) / 2)
        self.shake = 0
        if t >= self.next_wave and t < self.STRAFE_END:
            self.launch_wave()
            self.next_wave = t + rng.uniform(1.8, 2.6)
        for f in self.fighters:
            f["x"] += f["d"] * f["v"] * dt
            f["fire"] -= dt
            near = w.mx0 - 160 * u < f["x"] < w.mx1 + 160 * u
            if f["fire"] <= 0 and near and w.standing:
                b = rng.choice(list(w.standing.values()))
                tx, ty = w.ox + b.cx, w.oy + b.cy
                dx, dy = tx - f["x"], ty - f["y"]
                ln = math.hypot(dx, dy) or 1
                for off in (-5 * u, 5 * u):  # twin cannons
                    self.bolts.append({"x": f["x"], "y": f["y"] + off, "vx": dx / ln * 700 * u,
                                       "vy": dy / ln * 700 * u, "tx": tx, "ty": ty + off})
                f["fire"] = rng.uniform(.6, 1.0)
        self.fighters = [f for f in self.fighters if -200 * u < f["x"] < w.W + 200 * u]
        live = []
        for b in self.bolts:
            step = math.hypot(b["vx"], b["vy"]) * dt
            if math.hypot(b["tx"] - b["x"], b["ty"] - b["y"]) <= step:
                self.blasts.append([b["tx"], b["ty"], 8 * u, .1])  # the fighters only chip away
                w.smoke(b["tx"], b["ty"], rng.uniform(-15, 15) * u, -20 * u, rng.uniform(1, 2))
                self.shake = max(self.shake, 1.5 * u)
                continue
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            live.append(b)
        self.bolts = live
        for bl in self.blasts:
            bl[3] -= dt
        self.blasts = [bl for bl in self.blasts if bl[3] > 0]
        if self.CHARGE <= t < self.FIRE:
            self.shake = 1 * u
            if not self.aimed:  # aim the superlaser at whatever still stands
                self.aimed = True
                if w.standing:
                    bs = list(w.standing.values())
                    self.target = (w.ox + sum(b.cx for b in bs) / len(bs), w.oy + sum(b.cy for b in bs) / len(bs))
                else:
                    self.target = ((w.mx0 + w.mx1) / 2, w.ground - 10 * u)
        if t >= self.FIRE and not self.impacted:
            self.impacted = True
            for _ in range(40):
                a = rng.uniform(0, math.tau)
                sp = rng.uniform(10, 70) * u
                w.smoke(self.target[0], self.target[1], math.cos(a) * sp, math.sin(a) * sp * .6 - 20 * u, rng.uniform(2, 4.5))
        if self.impacted:
            e = t - self.FIRE
            self.flash = max(0.0, 1 - e / .4) * .8
            self.ring = 320 * u * e / .8 if e < .8 else -1
            self.shake = (9 if e < 1.2 else 3 if e < 2.2 else 0) * u
        if t > self.LEAVE + 2 and not self.fighters and not self.bolts:
            self.done = True

    def beam_on(self):
        return self.FIRE - .25 <= self.t < self.FIRE + 1.0

    def affect(self, x, y):
        u, rng = self.u, self.w.rng
        for bx, by, r, _ in self.blasts:
            d = math.hypot(x - bx, y - by)
            if d < r:
                d = max(d, 1)
                return (x - bx) / d * rng.uniform(80, 200) * u, (y - by) / d * 150 * u - 80 * u
        if self.beam_on():
            x0, y0 = self.dish()
            x1, y1 = self.target
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy) or 1
            k = max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / (ln * ln)))
            if math.hypot(x - (x0 + k * dx), y - (y0 + k * dy)) < 14 * u:
                return dx / ln * 300 * u, dy / ln * 200 * u - 150 * u
        if self.ring > 0:
            tx, ty = self.target
            d = math.hypot(x - tx, y - ty)
            if d < self.ring:
                d = max(d, 1)
                s = 480 * u * (1 - d / (320 * u)) + 90 * u
                return (x - tx) / d * s, (y - ty) / d * s - 120 * u
        return None

    def draw_ring(self, cr, front):
        """Half of the tilted ring: the back half before the planet, the front after."""
        u, R, x, y, a = self.u, self.R, self.sx, self.sy, self.alpha
        cr.save()
        cr.translate(x, y)
        cr.rotate(-.22 * self.side)
        cr.scale(2.1 * R, .42 * R)
        cr.arc(0, 0, 1, 0, math.pi) if front else cr.arc(0, 0, 1, math.pi, math.tau)
        cr.restore()
        cr.set_source_rgba(*STATION_HI, .85 * a)
        cr.set_line_width(5 * u)
        cr.stroke()

    def draw_back(self, cr):
        if self.alpha <= 0:
            return
        u, R, x, y, a = self.u, self.R, self.sx, self.sy, self.alpha
        self.draw_ring(cr, front=False)
        g = cairo.RadialGradient(x - .35 * R, y - .4 * R, R * .1, x, y, R)
        g.add_color_stop_rgba(0, *STATION_HI, a)
        g.add_color_stop_rgba(1, *STATION_LO, a)
        cr.set_source(g)
        cr.arc(x, y, R, 0, math.tau)
        cr.fill()
        cr.set_source_rgba(0, 0, 0, .15 * a)  # armour bands
        cr.set_line_width(1 * u)
        for k in (-.7, -.45, -.15, .2, .5):
            half = R * math.sqrt(1 - k * k)
            cr.move_to(x - half, y + k * R)
            cr.curve_to(x - half * .4, y + k * R + 6 * u, x + half * .4, y + k * R + 6 * u, x + half, y + k * R)
        cr.stroke()
        self.draw_ring(cr, front=True)
        dx, dy = self.dish()
        charging = self.CHARGE <= self.t < self.FIRE + 1.0
        cr.set_source_rgba(*STATION_LO, a)  # the emitter turret under the planet
        cr.move_to(dx - 9 * u, dy - 8 * u)
        cr.line_to(dx + 9 * u, dy - 8 * u)
        cr.line_to(dx + 5 * u, dy + 3 * u)
        cr.line_to(dx - 5 * u, dy + 3 * u)
        cr.close_path()
        cr.fill()
        if charging:
            k = min(1.0, (self.t - self.CHARGE) / (self.FIRE - self.CHARGE))
            glow = cairo.RadialGradient(dx, dy + 3 * u, 0, dx, dy + 3 * u, (10 + 30 * k) * u)
            glow.add_color_stop_rgba(0, *LASER_CORE, a)
            glow.add_color_stop_rgba(.3, *LASER, .8 * a)
            glow.add_color_stop_rgba(1, *LASER, 0)
            cr.set_source(glow)
            cr.arc(dx, dy + 3 * u, (10 + 30 * k) * u, 0, math.tau)
            cr.fill()
            if self.beam_on():
                cr.set_line_cap(1)
                for col, wd, al in ((LASER, 18, .35), (LASER, 9, .9), (LASER_CORE, 3, 1)):
                    cr.set_source_rgba(*col, al)
                    cr.set_line_width(wd * u * (1 + .12 * math.sin(self.t * 50)))
                    cr.move_to(dx, dy + 3 * u)
                    cr.line_to(*self.target)
                    cr.stroke()

    def draw_front(self, cr):
        u = self.u
        cr.set_line_cap(1)
        for b in self.bolts:
            ln = math.hypot(b["vx"], b["vy"]) or 1
            ex, ey = b["x"] - b["vx"] / ln * 16 * u, b["y"] - b["vy"] / ln * 16 * u
            for col, wd in ((LASER, 3.5), (LASER_CORE, 1.2)):
                cr.set_source_rgb(*col)
                cr.set_line_width(wd * u)
                cr.move_to(ex, ey)
                cr.line_to(b["x"], b["y"])
                cr.stroke()
        for f in self.fighters:  # delta-wing fighters with a hot engine at the back
            x, y, d = f["x"], f["y"] + math.sin(self.t * 5 + f["bob"]) * 2 * u, f["d"]
            cr.set_source_rgba(*ENGINE, .9)
            cr.arc(x - d * 11 * u, y, 2.6 * u, 0, math.tau)
            cr.fill()
            cr.set_source_rgb(*self.w.sil)
            cr.move_to(x + d * 13 * u, y)
            cr.line_to(x - d * 10 * u, y - 8 * u)
            cr.line_to(x - d * 6 * u, y)
            cr.line_to(x - d * 10 * u, y + 8 * u)
            cr.close_path()
            cr.fill()
        if self.impacted:
            e = self.t - self.FIRE
            tx, ty = self.target
            if e < 1.0:
                r = 90 * u * (.3 + e)
                fb = cairo.RadialGradient(tx, ty, 0, tx, ty, r)
                fb.add_color_stop_rgba(0, *LASER_CORE, 1 - e)
                fb.add_color_stop_rgba(.4, *FIRE2, .8 * (1 - e))
                fb.add_color_stop_rgba(1, *FIRE3, 0)
                cr.set_source(fb)
                cr.arc(tx, ty, r, 0, math.tau)
                cr.fill()
            if self.ring > 0:
                cr.set_source_rgba(*LASER, .6 * (1 - self.ring / (320 * u)))
                cr.set_line_width(3 * u)
                cr.arc(tx, ty, self.ring, 0, math.tau)
                cr.stroke()


DISASTERS = {"kaiju": Kaiju, "kraken": Kraken, "dragon": Dragon, "tripods": Tripods,
             "giant-ape": GiantApe, "ufo": UFO, "space-battle": SpaceBattle}
