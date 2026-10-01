"""Monument silhouettes, drawn as vector outlines and cut into bricks.

Each builder draws with a Pen whose y axis points up from the ground, in art
pixels for a 720-row scene. The mask is then split into bricks (6x4 by default) that the
workers place one by one, bottom-up.
"""

import math

import cairo

BW_, BH_ = 6, 4  # base block size; short cycles use bigger blocks


class Pen:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.surf = cairo.ImageSurface(cairo.FORMAT_A8, w, h)
        self.cr = cairo.Context(self.surf)
        self.cr.set_antialias(cairo.ANTIALIAS_NONE)
        self.cr.set_source_rgba(0, 0, 0, 1)

    def Y(self, yb):
        return self.h - yb

    def _fill(self):
        self.cr.fill()

    def cut(self):
        self.cr.set_operator(cairo.OPERATOR_CLEAR)

    def solid(self):
        self.cr.set_operator(cairo.OPERATOR_OVER)

    def rect(self, x0, yb0, x1, yb1):
        self.cr.rectangle(x0, self.Y(yb1), x1 - x0, yb1 - yb0)
        self._fill()

    def crect(self, cx, half, yb0, yb1):
        self.rect(cx - half, yb0, cx + half, yb1)

    def poly(self, pts):
        cr = self.cr
        cr.move_to(pts[0][0], self.Y(pts[0][1]))
        for x, y in pts[1:]:
            cr.line_to(x, self.Y(y))
        cr.close_path()
        self._fill()

    def circle(self, cx, cyb, r):
        self.cr.arc(cx, self.Y(cyb), r, 0, math.tau)
        self._fill()

    def ellipse(self, cx, cyb, rx, ry):
        cr = self.cr
        cr.save()
        cr.translate(cx, self.Y(cyb))
        cr.scale(rx, ry)
        cr.arc(0, 0, 1, 0, math.tau)
        cr.restore()
        self._fill()

    def line(self, x0, yb0, x1, yb1, width=1.0):
        cr = self.cr
        cr.set_line_width(width)
        cr.move_to(x0, self.Y(yb0))
        cr.line_to(x1, self.Y(yb1))
        cr.stroke()

    def profile(self, cx, half, yb0, yb1, step=2):
        """Symmetric shape whose half width at height yb is half(yb)."""
        ys = list(range(int(yb0), int(yb1), step)) + [yb1]
        left = [(cx - half(y), y) for y in ys]
        right = [(cx + half(y), y) for y in reversed(ys)]
        self.poly(left + right)

    def arch(self, cx, half, yb0, yb1, pointed=False):
        """Arch opening (round or pointed top) from yb0 up to yb1."""
        if pointed:
            spring = yb1 - half * 1.4
            self.poly([(cx - half, yb0), (cx - half, spring), (cx - half * .7, spring + half * .8), (cx, yb1),
                       (cx + half * .7, spring + half * .8), (cx + half, spring), (cx + half, yb0)])
        else:
            self.rect(cx - half, yb0, cx + half, yb1 - half)
            self.circle(cx, yb1 - half, half)


def eiffel(p):
    c = 130

    def half(y):
        return 5 + 125 * max(0.0, 1 - y / 372) ** 2.3

    p.profile(c, half, 0, 372)
    p.cut()
    p.ellipse(c, 0, 86, 92)
    for y0, y1 in ((4, 92), (118, 230), (246, 362)):
        for y in range(y0, y1 - 8, 12):
            for side in (-1, 1):
                outer = half(y) - 3
                inner = max(2, half(y) - (34 if y < 100 else 14 if y < 236 else 6))
                if y < 96:
                    arch = 86 * math.sqrt(max(0, 1 - (y / 92) ** 2))
                    inner = max(arch + 3, inner)
                if outer - inner > 5:
                    p.line(c + side * inner, y, c + side * outer, y + 10)
                    p.line(c + side * outer, y, c + side * inner, y + 10)
    p.profile(c, lambda y: max(0, half(y) - 16), 120, 228)
    p.profile(c, lambda y: max(0, half(y) - 5), 252, 356)
    p.solid()
    p.crect(c, half(100) + 8, 100, 114)
    p.crect(c, half(236) + 5, 232, 242)
    p.crect(c, 10, 372, 378)
    p.crect(c, 5, 378, 398)
    p.poly([(c - 2, 398), (c + 2, 398), (c, 440)])
    return 260, 440


def parthenon(p):
    c = 200
    for i, half in enumerate((200, 193, 186)):
        p.crect(c, half, i * 7, i * 7 + 7)
    for i in range(8):
        x = c - 168 + i * 48
        p.poly([(x - 11, 21), (x + 11, 21), (x + 9, 141), (x - 9, 141)])
        p.poly([(x - 9, 141), (x + 9, 141), (x + 13, 146), (x - 13, 146)])
        p.crect(x, 14, 146, 151)
    p.crect(c, 182, 151, 181)
    p.crect(c, 188, 181, 186)
    p.poly([(c - 188, 186), (c + 188, 186), (c, 226)])
    for x, y in ((c - 186, 186), (c + 186, 186), (c, 224)):
        p.crect(x, 3, y, y + 7)
    p.cut()
    for i in range(30):
        x = c - 176 + i * 12.2
        p.rect(x, 168, x + 2, 178)
    p.solid()
    return 400, 233


def giza(p):
    def pyramid(cx, half, base, height):
        p.poly([(cx - half, base), (cx + half, base), (cx, base + height)])

    pyramid(430, 140, 0, 186)
    pyramid(215, 160, 0, 203)
    pyramid(600, 58, 0, 74)
    # the Sphinx, lying in front
    p.poly([(4, 0), (96, 0), (96, 10), (88, 16), (40, 18), (30, 16), (20, 14), (8, 8)])
    p.poly([(14, 10), (34, 10), (36, 30), (30, 36), (20, 36), (14, 30)])
    p.poly([(12, 22), (38, 22), (34, 34), (16, 34)])
    p.rect(0, 0, 22, 5)
    return 660, 210


def empire_state(p):
    c = 86
    p.crect(c, 84, 0, 26)
    p.crect(c, 72, 26, 96)
    p.crect(c, 56, 96, 262)
    p.crect(c, 49, 262, 292)
    p.crect(c, 40, 292, 318)
    p.crect(c, 31, 318, 338)
    p.poly([(c - 26, 338), (c + 26, 338), (c + 20, 352), (c - 20, 352)])
    p.poly([(c - 11, 352), (c + 11, 352), (c + 7, 398), (c - 7, 398)])
    p.poly([(c - 3, 398), (c + 3, 398), (c + .5, 450), (c - .5, 450)])
    p.cut()
    for k in range(-7, 8):
        p.rect(c + k * 7, 102, c + k * 7 + 1, 256)
    for k in range(-9, 10):
        p.rect(c + k * 7, 30, c + k * 7 + 1, 90)
    for k in range(-5, 6):
        p.rect(c + k * 8, 268, c + k * 8 + 1, 288)
    p.solid()
    return 172, 450


def big_ben(p):
    tx = 300
    # Palace of Westminster
    p.rect(0, 0, tx - 20, 72)
    for x in range(4, tx - 22, 14):
        p.poly([(x - 2, 72), (x + 2, 72), (x, 86)])
    for x, w, h in ((24, 9, 104), (110, 7, 96), (190, 8, 108)):
        p.crect(x, w, 72, h)
        p.poly([(x - w - 1, h), (x + w + 1, h), (x, h + 22)])
    p.cut()
    for row in (10, 40):
        for x in range(8, tx - 26, 9):
            p.rect(x, row, x + 2, row + 20)
    p.solid()
    # Elizabeth Tower
    p.crect(tx, 22, 0, 252)
    p.crect(tx, 27, 252, 302)
    p.crect(tx, 24, 302, 324)
    p.crect(tx, 27, 324, 330)
    p.poly([(tx - 23, 330), (tx + 23, 330), (tx, 388)])
    for dx in (-25, 25):
        p.poly([(tx + dx - 2, 324), (tx + dx + 2, 324), (tx + dx, 356)])
    p.poly([(tx - 1.5, 386), (tx + 1.5, 386), (tx, 412)])
    p.cut()
    for dx in (-11, 0, 11):
        p.rect(tx + dx, 24, tx + dx + 1, 244)
    p.circle(tx, 277, 17)
    for dx in (-12, 0, 12):
        p.arch(tx + dx, 3, 306, 320)
    p.solid()
    p.circle(tx, 277, 13)
    p.cut()
    p.line(tx, 277, tx, 287, 1.5)
    p.line(tx, 277, tx + 7, 274, 1.5)
    p.solid()
    return tx + 30, 412


def taj_mahal(p):
    c = 220
    p.crect(c, 220, 0, 14)
    for mx in (c - 202, c + 202):
        p.poly([(mx - 7, 14), (mx + 7, 14), (mx + 5, 218), (mx - 5, 218)])
        for y in (72, 134, 196):
            p.crect(mx, 9, y, y + 4)
        p.crect(mx, 8, 218, 226)
        p.ellipse(mx, 226, 8, 9)
        p.line(mx, 230, mx, 246, 1.5)
    p.crect(c, 116, 14, 142)
    p.crect(c, 42, 142, 160)
    for dx in (-112, -42, 42, 112):
        p.poly([(c + dx - 2, 142), (c + dx + 2, 142), (c + dx, 172 if abs(dx) == 42 else 160)])
    p.crect(c, 54, 142, 178)

    def dome(y):
        if y <= 214:
            return 54 + 12 * math.sin((y - 178) / 36 * math.pi / 2)
        u = (y - 214) / 70
        return 66 * math.cos(u * math.pi / 2) ** 1.15
    p.profile(c, dome, 178, 284)
    p.line(c, 280, c, 304, 2)
    p.circle(c, 292, 3)
    for dx in (-84, 84):
        p.crect(c + dx, 13, 142, 160)
        p.ellipse(c + dx, 160, 14, 15)
        p.line(c + dx, 170, c + dx, 184, 1.5)
    p.cut()
    p.arch(c, 26, 22, 128, pointed=True)
    for dx in (-74, 74):
        p.arch(c + dx, 13, 24, 74, pointed=True)
        p.arch(c + dx, 13, 84, 134, pointed=True)
    for dx in (-104, 104):
        p.arch(c + dx, 6, 24, 60, pointed=True)
        p.arch(c + dx, 6, 74, 110, pointed=True)
    for dx in (-84, 84):
        p.rect(c + dx - 8, 144, c + dx - 2, 156)
        p.rect(c + dx + 2, 144, c + dx + 8, 156)
    p.solid()
    return 440, 304


def colosseum(p):
    def top(x):
        if x < 300:
            return 178
        if x < 332:
            return 160 - (x - 300) * .3
        if x < 372:
            return 124 + 6 * math.sin(x * .7)
        if x < 430:
            return 86 + 4 * math.sin(x * 1.3)
        return 82 - (x - 430) * .5

    pts = [(0, 0)] + [(x, top(x)) for x in range(0, 481, 2)] + [(480, 0)]
    p.poly(pts)
    p.cut()
    for tier in range(3):
        base = tier * 40
        for i in range(16):
            x = 15 + i * 30
            if top(x - 8) > base + 40 and top(x + 8) > base + 40:
                p.arch(x, 8, base + 4, base + 32)
    for x in range(30, 300, 60):
        p.rect(x, 140, x + 7, 151)
    p.solid()
    return 480, 178


def opera_house(p):
    base = 34
    p.rect(40, 0, 520, base)
    for i in range(8):
        p.rect(i * 5, 0, 40, (i + 1) * base / 8)

    def shell(xl, xr, ax, ay, lean):
        cr = p.cr
        cr.move_to(xl, p.Y(base))
        if lean < 0:
            cr.curve_to(xl, p.Y(base + ay * .5), ax - 10, p.Y(ay * .95), ax, p.Y(ay))
            cr.curve_to(ax + (xr - ax) * .45, p.Y(ay * .8), xr - 6, p.Y(base + 16), xr, p.Y(base))
        else:
            cr.curve_to(xl + 6, p.Y(base + 16), ax - (ax - xl) * .45, p.Y(ay * .8), ax, p.Y(ay))
            cr.curve_to(ax + 10, p.Y(ay * .95), xr, p.Y(base + ay * .5), xr, p.Y(base))
        cr.close_path()
        cr.fill()

    shell(60, 150, 70, 118, -1)
    shell(100, 214, 114, 168, -1)
    shell(160, 270, 172, 196, -1)
    shell(232, 304, 296, 138, 1)
    shell(300, 372, 312, 112, -1)
    shell(334, 420, 348, 142, -1)
    shell(392, 470, 460, 104, 1)
    p.cut()
    for shell_x, ay in ((70, 118), (114, 168), (172, 196), (312, 112), (348, 142)):
        p.line(shell_x + 3, ay - 6, shell_x + 30, base + 6, 1)
    p.solid()
    return 520, 200


def burj_khalifa(p):
    c = 86
    tiers = [(58, 72, 72), (118, 60, 66), (176, 54, 56), (226, 46, 50), (270, 38, 44), (310, 32, 35),
             (346, 26, 29), (376, 20, 22), (402, 15, 17), (424, 10, 12)]
    y0 = 0
    for y1, lh, rh in tiers:
        p.rect(c - lh, y0, c + rh, y1)
        y0 = y1
    p.poly([(c - 8, 424), (c + 9, 424), (c + 1, 482), (c, 482)])
    p.cut()
    p.rect(c, 20, c + 1, 400)
    p.solid()
    return 172, 482


# ---------------------------------------------------------------- the Ancient Wonders

def limb(p, x0, y0, x1, y1, w0, w1):
    """Tapered limb from (x0, y0) with width w0 to (x1, y1) with width w1."""
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln, dx / ln
    p.poly([(x0 + nx * w0 / 2, y0 + ny * w0 / 2), (x1 + nx * w1 / 2, y1 + ny * w1 / 2),
            (x1 - nx * w1 / 2, y1 - ny * w1 / 2), (x0 - nx * w0 / 2, y0 - ny * w0 / 2)])


def palm(p, x, base, h, lean=0):
    tx = x + lean
    limb(p, x, base, tx, base + h, 4, 2.5)
    for ang in (-160, -130, -100, -75, -50, -20):
        a = math.radians(ang)
        ex, ey = tx + math.cos(a) * 15, base + h + math.sin(-a) * 6 - 7
        mx, my = tx + math.cos(a) * 8, base + h + 4
        limb(p, tx, base + h, mx, my, 3, 2.5)
        limb(p, mx, my, ex, ey, 2.5, 1)


def hanging_gardens(p):
    c = 240
    tiers = [(0, 240, 54), (54, 196, 50), (104, 152, 46), (150, 108, 42)]
    for y0, hw, ht in tiers:
        p.crect(c, hw, y0, y0 + ht)
        for x in range(int(c - hw), int(c + hw) - 4, 10):
            p.rect(x, y0 + ht, x + 5, y0 + ht + 3)
    p.crect(c, 44, 192, 214)
    p.crect(c, 48, 214, 218)
    p.cut()
    for y0, hw, ht in tiers:
        n = int((2 * hw - 24) // 28)
        for i in range(n):
            x = c - (n - 1) * 14 + i * 28
            p.arch(x, 7, y0 + 6, y0 + ht - 8)
    p.solid()
    # greenery on each terrace and vines hanging over the arches
    for i, (y0, hw, ht) in enumerate(tiers):
        top = y0 + ht + 3
        inner = tiers[i + 1][1] if i + 1 < len(tiers) else 44
        for side in (-1, 1):
            span = hw - inner
            for k in range(max(1, int(span // 16))):
                x = c + side * (inner + 8 + k * 16)
                if (k + i) % 2 == 0:
                    palm(p, x, top, 26 - i * 2, lean=side * 3)
                else:
                    for dx, dy, r in ((-5, 6, 6), (5, 7, 6), (0, 12, 7)):
                        p.circle(x + dx, top + dy, r)
        for x in range(int(c - hw) + 6, int(c + hw) - 6, 7):
            drop = 6 + (x * 37 % 23)
            p.line(x, y0 + ht, x + (x % 3) - 1, y0 + ht - drop, 1.2)
    palm(p, c - 30, 218, 30, -4)
    palm(p, c + 30, 218, 34, 4)


def temple_of_artemis(p):
    c = 230
    for i in range(6):
        p.crect(c, 230 - i * 5, i * 5, i * 5 + 5)
    for i in range(10):
        x = c - 200 + i * 400 / 9
        p.crect(x, 9, 30, 34)
        p.poly([(x - 7, 34), (x + 7, 34), (x + 6, 180), (x - 6, 180)])
        p.crect(x, 11, 180, 186)
        for dx in (-9, 9):
            p.circle(x + dx, 181, 4)
    p.crect(c, 214, 186, 206)
    p.crect(c, 220, 206, 211)
    p.poly([(c - 220, 211), (c + 220, 211), (c, 252)])
    for x, y in ((c - 214, 211), (c + 214, 211), (c, 248)):
        p.crect(x, 4, y, y + 12)
        p.circle(x, y + 15, 4)
    p.cut()
    p.rect(c - 9, 218, c + 9, 236)
    for dx in (-44, 44):
        p.rect(c + dx - 6, 218, c + dx + 6, 228)
    p.solid()


def statue_of_zeus(p):
    # seated Zeus on his throne, in profile facing left
    p.rect(10, 0, 256, 40)
    p.rect(4, 36, 262, 44)
    p.rect(150, 44, 246, 150)                          # throne seat
    p.rect(222, 150, 246, 296)                         # throne back
    p.circle(234, 301, 9)
    p.rect(146, 150, 222, 160)                         # armrest
    p.poly([(52, 44), (104, 44), (100, 140), (200, 146), (204, 178), (72, 176), (58, 160)])  # robed legs
    p.poly([(148, 172), (204, 172), (206, 236), (196, 262), (152, 262), (142, 236)])        # torso
    p.rect(160, 256, 182, 272)
    p.circle(170, 286, 16)                             # head
    p.poly([(156, 282), (162, 256), (178, 262), (172, 278)])  # beard
    for a in range(30, 181, 25):                       # olive wreath
        r = math.radians(a)
        p.circle(170 + math.cos(r) * 15, 288 + math.sin(r) * 13, 3.5)
    limb(p, 158, 250, 132, 214, 18, 14)                # right arm forward
    limb(p, 132, 214, 98, 212, 14, 11)
    p.poly([(88, 214), (100, 214), (98, 238), (90, 238)])  # Nike on his hand
    p.circle(94, 243, 4)
    p.poly([(98, 230), (112, 248), (102, 226)])
    limb(p, 196, 254, 206, 294, 16, 12)                # left arm up to the sceptre
    p.rect(203, 44, 209, 352)
    p.poly([(196, 352), (216, 352), (212, 360), (206, 364), (200, 360)])  # eagle
    p.poly([(188, 356), (198, 353), (196, 360)])
    p.poly([(224, 356), (214, 353), (216, 360)])


def mausoleum(p):
    c = 150
    p.crect(c, 136, 0, 8)
    p.crect(c, 128, 8, 100)
    p.crect(c, 134, 100, 106)
    for i in range(11):
        x = c - 110 + i * 22
        p.crect(x, 5, 106, 112)
        p.crect(x, 4, 112, 164)
        p.crect(x, 6, 164, 168)
    p.crect(c, 122, 168, 182)
    for i in range(12):
        p.crect(c, 118 - i * 6.5, 182 + i * 6, 188 + i * 6)
    p.crect(c, 40, 254, 260)
    # quadriga: chariot, driver and four horses
    p.rect(c, 260, c + 26, 278)
    p.circle(c + 13, 264, 9)
    p.crect(c + 12, 4, 278, 294)
    p.circle(c + 12, 298, 4)
    for k in range(4):
        hx = c - 6 - k * 4
        p.ellipse(hx - 14, 276 + k, 17, 7)
        limb(p, hx - 26, 278 + k, hx - 34, 292 + k, 7, 5)
        p.ellipse(hx - 37, 293 + k, 6, 3.5)
        for lx in (hx - 26, hx - 4):
            p.line(lx, 272 + k, lx - 2, 260, 2)


def colossus(p):
    c = 120
    for x0 in (24, 150):
        p.rect(x0, 0, x0 + 66, 56)
        p.rect(x0 - 4, 52, x0 + 70, 60)
    for sgn in (-1, 1):
        fx = c + sgn * 63
        p.poly([(fx - 14, 60), (fx + 14, 60), (fx + 10, 68), (fx - 10, 68)])
        limb(p, fx, 64, c + sgn * 40, 136, 18, 25)        # shin
        limb(p, c + sgn * 40, 136, c + sgn * 16, 210, 25, 34)  # thigh
    p.poly([(86, 200), (154, 200), (160, 232), (80, 232)])     # hips
    p.poly([(82, 228), (158, 228), (150, 262), (168, 300), (72, 300), (90, 262)])  # torso
    p.rect(110, 296, 130, 314)
    p.circle(c, 326, 16)
    for a in range(10, 171, 26):                               # radiant crown
        r = math.radians(a)
        bx, by = c + math.cos(r) * 14, 326 + math.sin(r) * 14
        tx, ty = c + math.cos(r) * 32, 326 + math.sin(r) * 32
        nx, ny = -math.sin(r) * 3.5, math.cos(r) * 3.5
        p.poly([(bx + nx, by + ny), (tx, ty), (bx - nx, by - ny)])
    limb(p, 82, 292, 66, 344, 22, 17)          # right arm raised with the torch
    limb(p, 66, 344, 62, 392, 17, 13)
    p.rect(55, 388, 69, 410)
    p.poly([(51, 410), (73, 410), (69, 420), (62, 434), (55, 420)])
    limb(p, 160, 292, 176, 248, 22, 17)        # left arm down, cloak over it
    limb(p, 176, 248, 182, 212, 17, 13)
    p.poly([(164, 292), (190, 246), (196, 150), (182, 140), (174, 214), (158, 272)])


def lighthouse(p):
    c = 100
    p.crect(c, 100, 0, 14)
    p.poly([(c - 64, 14), (c + 64, 14), (c + 54, 230), (c - 54, 230)])
    p.crect(c, 60, 230, 238)
    p.poly([(c - 40, 238), (c + 40, 238), (c + 34, 330), (c - 34, 330)])
    p.crect(c, 38, 330, 336)
    p.crect(c, 24, 336, 384)
    p.crect(c, 27, 384, 390)
    p.ellipse(c, 390, 18, 10)
    p.poly([(c - 4, 398), (c + 4, 398), (c + 3, 424), (c - 3, 424)])  # statue on top
    p.circle(c, 429, 4.5)
    p.line(c + 7, 398, c + 7, 446, 2)
    limb(p, c + 2, 420, c + 7, 432, 3, 2)
    p.cut()
    for y in range(44, 220, 30):
        for dx in (-30, 0, 30):
            p.rect(c + dx - 2, y, c + dx + 2, y + 9)
    for y in (260, 296):
        p.rect(c - 3, y, c + 3, y + 12)
    for dx in (-12, 0, 12):
        p.rect(c + dx - 3, 344, c + dx + 3, 376)
    p.solid()


# ---------------------------------------------------------------- more wonders

def onion(p, cx, base, r, tip):
    """An onion dome sitting at height base, widest r, ending in a point at tip."""
    def half(y):
        k = (y - base) / (tip - base)
        if k < .45:
            return r * (0.75 + 0.25 * math.sin(k / .45 * math.pi / 2))
        return r * math.cos((k - .45) / .55 * math.pi / 2) ** 1.6
    p.profile(cx, half, base, tip)


def chichen_itza(p):
    c = 210
    for i in range(9):
        half, y0 = 200 - 17 * i, i * 18
        p.poly([(c - half, y0), (c + half, y0), (c + half - 5, y0 + 18), (c - half + 5, y0 + 18)])
    p.crect(c, 30, 0, 162)                      # the great stairway up the middle
    for dx in (-36, 36):                        # serpent heads at its foot
        p.ellipse(c + dx, 6, 9, 7)
    p.crect(c, 46, 162, 198)                    # temple on top
    p.crect(c, 50, 198, 204)
    for x in range(c - 44, c + 45, 11):
        p.rect(x, 204, x + 6, 212)
    p.cut()
    for dx in (-24, 0, 24):
        p.rect(c + dx - 5, 166, c + dx + 5, 188)
    p.solid()


def stonehenge(p):
    stones = [(20, 18, 80), (52, 18, 84), (84, 17, 82), (150, 18, 80), (182, 18, 84),
              (292, 18, 82), (324, 17, 80), (390, 18, 84), (422, 18, 80), (454, 17, 78)]
    for x, w, h in stones:
        p.poly([(x - w / 2, 0), (x + w / 2, 0), (x + w / 2 - 2, h), (x - w / 2 + 2, h)])
    for x0, x1, h in ((14, 92, 80), (144, 190, 80), (286, 332, 80), (384, 430, 80)):
        p.rect(x0, h, x1, h + 10)                # lintels resting on the uprights
    for x, h in ((228, 112), (256, 112)):        # the great trilithon in the middle
        p.poly([(x - 11, 0), (x + 11, 0), (x + 9, h), (x - 9, h)])
    p.rect(214, 112, 270, 124)
    for x in (118, 360):                         # small bluestones in front
        p.poly([(x - 6, 0), (x + 6, 0), (x + 4, 30), (x - 4, 30)])
    p.rect(100, 0, 140, 9)                       # a fallen stone


def statue_of_liberty(p):
    c = 100
    p.crect(c, 98, 0, 18)                        # star-fort base
    p.crect(c, 82, 18, 40)
    p.poly([(c - 62, 40), (c + 62, 40), (c + 50, 170), (c - 50, 170)])  # pedestal
    p.crect(c, 56, 170, 178)
    p.crect(c, 46, 178, 200)
    p.crect(c, 40, 200, 206)
    p.poly([(c - 30, 206), (c + 32, 206), (c + 26, 360), (c - 24, 360)])  # robed figure
    p.poly([(c - 30, 206), (c - 40, 206), (c - 28, 300), (c - 22, 300)])  # drapery folds
    p.circle(c + 1, 378, 12)
    p.rect(c - 5, 356, c + 7, 370)
    for a in range(20, 161, 23):                 # crown rays
        r = math.radians(a)
        bx, by = c + 1 + math.cos(r) * 11, 380 + math.sin(r) * 11
        tx, ty = c + 1 + math.cos(r) * 27, 380 + math.sin(r) * 27
        nx, ny = -math.sin(r) * 2.5, math.cos(r) * 2.5
        p.poly([(bx + nx, by + ny), (tx, ty), (bx - nx, by - ny)])
    limb(p, c - 20, 352, c - 32, 404, 14, 11)    # right arm up with the torch
    limb(p, c - 32, 404, c - 37, 440, 11, 9)
    p.rect(c - 43, 438, c - 31, 452)
    p.poly([(c - 47, 452), (c - 27, 452), (c - 31, 462), (c - 37, 474), (c - 43, 462)])
    limb(p, c + 22, 350, c + 32, 318, 13, 11)    # left arm holding the tablet
    p.poly([(c + 22, 296), (c + 44, 300), (c + 40, 344), (c + 18, 340)])


def leaning_tower(p):
    lean = math.tan(math.radians(4.5))
    p.cr.transform(cairo.Matrix(1, 0, -lean, 1, lean * p.h, 0))  # tilt the whole tower
    c = 64
    p.crect(c, 48, 0, 6)
    p.crect(c, 45, 6, 44)
    for i in range(6):
        y0 = 44 + i * 34
        p.crect(c, 47, y0, y0 + 4)               # gallery floor
        p.crect(c, 44, y0 + 4, y0 + 34)
    p.crect(c, 47, 248, 252)
    p.crect(c, 32, 252, 284)                     # belfry
    p.crect(c, 35, 284, 288)
    p.cut()
    for i in range(6):
        y0 = 44 + i * 34
        for k in range(-3, 4):
            p.arch(c + k * 12, 3.5, y0 + 7, y0 + 28)
    for k in range(-2, 3):
        p.arch(c + k * 12, 3.5, 256, 278)
    for k in range(-3, 4):
        p.arch(c + k * 12, 3.5, 10, 36)
    p.solid()


def st_basils(p):
    c = 180
    p.crect(c, 172, 0, 70)                       # gallery building
    p.crect(c + 168, 12, 70, 150)                # bell tower
    p.poly([(c + 154, 150), (c + 182, 150), (c + 168, 200)])
    p.line(c + 168, 198, c + 168, 214, 1.5)
    p.crect(c, 26, 70, 172)                      # central tower and its tent roof
    p.poly([(c - 26, 172), (c + 26, 172), (c, 252)])
    onion(p, c, 250, 7, 266)
    p.line(c, 264, c, 286, 1.5)
    p.line(c - 4, 280, c + 4, 280, 1.5)
    for dx, top, r in ((-112, 136, 22), (-58, 168, 20), (58, 168, 20), (112, 128, 22), (-150, 98, 13), (150, 96, 13)):
        x = c + dx
        p.crect(x, r * .78, 70, top)             # drum
        onion(p, x, top, r, top + r * 2.6)
        tip = top + r * 2.6
        p.line(x, tip - 2, x, tip + 14, 1.4)
        p.line(x - 3, tip + 10, x + 3, tip + 10, 1.4)
    p.cut()
    for x in range(c - 160, c + 150, 22):
        p.arch(x, 6, 10, 46)
    p.solid()


def petra(p):
    c = 150
    p.crect(c, 150, 0, 8)
    for dx in (-118, -66, -22, 22, 66, 118):    # lower colonnade
        p.crect(c + dx, 9, 8, 12)
        p.crect(c + dx, 7, 12, 146)
        p.crect(c + dx, 10, 146, 152)
    p.crect(c, 140, 152, 168)
    p.poly([(c - 76, 168), (c + 76, 168), (c, 198)])  # pediment over the portico
    p.crect(c, 132, 198, 204)                    # attic
    for side in (-1, 1):                         # side pavilions with broken pediments
        x0, x1 = (c + side * 82, c + side * 134)
        p.rect(min(x0, x1), 204, max(x0, x1), 266)
        p.poly([(x0, 266), (x1, 266), (x0, 284)])
    p.crect(c, 32, 204, 274)                     # the round tholos
    p.poly([(c - 34, 274), (c + 34, 274), (c, 300)])
    p.circle(c, 306, 7)
    p.cut()
    for dx in (-20, 0, 20):
        p.rect(c + dx - 4, 210, c + dx + 4, 266)
    for side in (-1, 1):
        for dx in (96, 120):
            p.rect(c + side * dx - 4, 210, c + side * dx + 4, 260)
    p.rect(c - 14, 8, c + 14, 120)               # the dark doorway
    p.solid()


MONUMENTS = {
    "eiffel": eiffel, "parthenon": parthenon, "giza": giza, "empire-state": empire_state,
    "big-ben": big_ben, "taj-mahal": taj_mahal, "colosseum": colosseum,
    "opera-house": opera_house, "burj-khalifa": burj_khalifa,
    # the rest of the Seven Wonders of the Ancient World (Giza is above)
    "hanging-gardens": hanging_gardens, "temple-of-artemis": temple_of_artemis,
    "statue-of-zeus": statue_of_zeus, "mausoleum": mausoleum, "colossus": colossus,
    "lighthouse": lighthouse,
    # more wonders
    "chichen-itza": chichen_itza, "stonehenge": stonehenge, "statue-of-liberty": statue_of_liberty,
    "leaning-tower": leaning_tower, "st-basils": st_basils, "petra": petra,
}
SIZES = {"eiffel": (260, 444), "parthenon": (400, 233), "giza": (660, 210), "empire-state": (172, 452),
         "big-ben": (330, 414), "taj-mahal": (440, 306), "colosseum": (480, 180),
         "opera-house": (520, 200), "burj-khalifa": (172, 484),
         "hanging-gardens": (480, 260), "temple-of-artemis": (460, 268), "statue-of-zeus": (266, 368),
         "mausoleum": (300, 304), "colossus": (240, 436), "lighthouse": (200, 450),
         "chichen-itza": (420, 214), "stonehenge": (480, 126), "statue-of-liberty": (200, 476),
         "leaning-tower": (160, 290), "st-basils": (370, 290), "petra": (300, 314)}
# Where a fire burns once the monument stands (x, height above ground), lit at night.
BEACONS = {"lighthouse": (100, 360), "colossus": (62, 424), "statue-of-liberty": (63, 462)}


class Brick:
    __slots__ = ("gx", "gy", "runs", "cx", "cy", "top", "bottom", "placed", "taken", "hanging")

    def __init__(self, gx, gy, runs):
        self.gx, self.gy, self.runs = gx, gy, runs
        xs = [x for x, _, n in runs] + [x + n for x, _, n in runs]
        ys = [y for _, y, _ in runs]
        self.cx = (min(xs) + max(xs)) / 2
        self.top, self.bottom = min(ys), max(ys) + 1
        self.cy = (self.top + self.bottom) / 2
        self.placed = False
        self.taken = False  # assigned to a worker
        self.hanging = False  # only held from above (vines, drapery), not built up from below


class Monument:
    def __init__(self, name, rng, scale=1.0, block=1.0):
        self.name = name
        self.bw, self.bh = BW, BH = round(BW_ * block), round(BH_ * block)
        sw, sh = SIZES[name]
        w, h = int(sw * scale) + 2, int(sh * scale) + 2
        pen = Pen(w, h)
        pen.cr.scale(scale, scale)
        pen.h = h / scale
        MONUMENTS[name](pen)
        pen.surf.flush()
        data, stride = pen.surf.get_data(), pen.surf.get_stride()
        mask = [[data[y * stride + x] > 127 for x in range(w)] for y in range(h)]
        # trim empty rows at the top
        while mask and not any(mask[0]):
            mask.pop(0)
        h = len(mask)
        self.w, self.h = w, h
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
                    bricks.append(Brick(gx, gy, runs))
        self.mask = mask
        # Bricks that can be stacked up from the ground (each resting on one below it
        # or beside it); the rest hang from something above and go in after it.
        grid = {(b.gx, b.gy): b for b in bricks}
        stack = [b for b in bricks if b.gy == 0]
        seen = {(b.gx, b.gy) for b in stack}
        while stack:
            b = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (0, 1):
                    k = (b.gx + dx, b.gy + dy)
                    if k in grid and k not in seen:
                        seen.add(k)
                        stack.append(grid[k])
        for k, b in grid.items():
            b.hanging = k not in seen
        self.bricks = sorted(bricks, key=lambda b: b.gy + rng.uniform(0, 1.6))
