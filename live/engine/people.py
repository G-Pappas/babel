"""The construction crew: how a worker is drawn, and what each one does.

Behaviour is written as generators: each job yields once per frame and reads
the frame time from self.dt, so a job reads like a to-do list
(walk to the pallet, pick up blocks, climb, place each block, come back down).
"""

import math

from .site import INSTALL_TIME, draw_ladder

WALK, CARRY_WALK, CLIMB, RUN = 20.0, 15.0, 10.0, 46.0
THIGH, SHIN, TORSO, UPPER, FORE = 4.6, 4.4, 6.2, 3.4, 3.2


def _seg(x, y, angle, length, f):
    """End of a limb hanging at `angle` from straight down (positive = forward)."""
    return x + math.sin(angle) * length * f, y + math.cos(angle) * length


def draw_person(cr, x, y, f, pose, ph, carry=0, rot=0.0, lift=0.0, poles=0):
    """Silhouette worker with a hard hat; (x, y) are the feet, f the facing."""
    s = math.sin(ph)
    c = math.cos(ph)
    lean = 0.05
    if pose in ("walk", "carry", "run"):
        amp = .62 if pose == "run" else .45
        legs = [(amp * s, amp * s - .8 * max(0, c)), (-amp * s, -amp * s - .8 * max(0, -c))]
        if pose == "carry":
            arms = [(1.1, 1.6), (1.0, 1.5)]
        elif pose == "run":
            arms = [(math.pi - .5 + .4 * s, math.pi - .3), (math.pi - .5 - .4 * s, math.pi - .3)]
            lean = .25
        else:
            arms = [(-.45 * s, -.45 * s + .35), (.45 * s, .45 * s + .35)]
    elif pose == "climb":
        k1, k2 = max(0, s), max(0, -s)
        legs = [(1.2 * k1, 1.2 * k1 - 1.9 * k1), (1.2 * k2, 1.2 * k2 - 1.9 * k2)]
        arms = [(math.pi - .5 + .35 * s, math.pi - .2), (math.pi - .5 - .35 * s, math.pi - .2)]
        lean = .12
    elif pose == "bend":
        legs = [(.5, -.4), (.3, -.5)]
        arms = [(.9, .9), (.8, .8)]
        lean = .9
    elif pose == "place":
        legs = [(.15, 0), (-.1, 0)]
        arms = [(2.0 + lift, 2.1 + lift), (1.9 + lift, 2.0 + lift)]
        lean = .25
    elif pose == "sit":
        legs = [(1.57, .2), (1.5, .3)]
        arms = [(.5, 1.1), (.4, 1.0)]
        lean = -.05
    elif pose == "talk":
        g = .4 + .3 * math.sin(ph * .7)
        legs = [(.08, 0), (-.08, 0)]
        arms = [(g, g + .9), (.1, .2)]
    elif pose == "dance":
        kick = max(0, s)
        legs = [(.9 * kick, -.9 * kick), (-.15 * max(0, -s), 0)]
        arms = [(math.pi - .7 + .5 * s, math.pi - .2 + .4 * c), (math.pi - .7 - .5 * s, math.pi - .2 - .4 * c)]
        lean = .1 * c
    elif pose == "cheer":
        legs = [(.15, 0), (-.15, 0)]
        arms = [(math.pi - .5 + .2 * s, math.pi - .3), (math.pi - .5 - .2 * s, math.pi - .3)]
    elif pose == "tumble":
        legs = [(.9 + s, .4), (-.6 - s, -.2)]
        arms = [(2.2 + c, 2.6), (-2.0 - c, -2.4)]
    else:  # stand
        legs = [(.06, 0), (-.06, 0)]
        arms = [(.12, .2), (-.05, .05)]

    # place the hip so the lowest foot touches y
    drops = [math.cos(t) * THIGH + math.cos(k) * SHIN for t, k in legs]
    hip_y = y - max(drops) if pose != "sit" else y - 3.2
    hip_x = x

    cr.save()
    if rot:
        cr.translate(x, y - 9)
        cr.rotate(rot)
        cr.translate(-x, -(y - 9))
    cr.set_line_cap(1)  # round
    cr.set_line_join(1)
    sx = hip_x + math.sin(lean) * TORSO * f
    sy = hip_y - math.cos(lean) * TORSO
    cr.set_line_width(1.9)
    for t, k in legs:
        kx, ky = _seg(hip_x, hip_y, t, THIGH, f)
        fx, fy = _seg(kx, ky, k, SHIN, f)
        cr.move_to(hip_x, hip_y)
        cr.line_to(kx, ky)
        cr.line_to(fx, fy)
        cr.line_to(fx + 1.1 * f, fy)
    cr.stroke()
    cr.set_line_width(3.3)
    cr.move_to(hip_x, hip_y)
    cr.line_to(sx, sy)
    cr.stroke()
    cr.set_line_width(1.5)
    hands = []
    for u, fo in arms:
        ex, ey = _seg(sx, sy + .6, u, UPPER, f)
        hx, hy = _seg(ex, ey, fo, FORE, f)
        cr.move_to(sx, sy + .6)
        cr.line_to(ex, ey)
        cr.line_to(hx, hy)
        hands.append((hx, hy))
    cr.stroke()
    hx = sx + math.sin(lean) * 2.6 * f
    hy = sy - math.cos(lean) * 2.6
    cr.arc(hx, hy, 1.9, 0, math.tau)
    cr.fill()
    # hard hat: dome plus brim
    cr.arc(hx, hy - .5, 2.3, math.pi, 0)
    cr.fill()
    cr.rectangle(hx - 2.2 + .9 * f, hy - .9, 4.4, .9)
    cr.fill()
    if carry and pose in ("carry", "climb", "bend"):
        bx = (hands[0][0] + hands[1][0]) / 2
        by = (hands[0][1] + hands[1][1]) / 2
        if pose == "climb":
            bx, by = sx - 3.5 * f, sy + 5  # strapped on the back
        for i in range(min(carry, 3)):
            cr.rectangle(bx - 3, by - 3.5 - i * 4.4, 6, 4)
        cr.fill()
    if poles:  # ladder sections over the shoulder (upright on the back while climbing)
        for i in range(min(poles, 3)):
            if pose == "climb":
                draw_ladder(cr, sx - (4 + i * 1.5) * f, sy + 10, sx - (4 + i * 1.5) * f, sy - 10, 2.4)
            else:
                draw_ladder(cr, sx - 10 * f, sy + 1.5 - i * 1.6, sx + 9 * f, sy - 3.5 - i * 1.6, 2.4)
    cr.restore()


class Worker:
    def __init__(self, world, x, rng):
        self.w = world
        self.rng = rng
        self.x, self.y = x, world.ground
        self.level = 0
        self.f = rng.choice((-1, 1))
        self.pose = "stand"
        self.ph = rng.uniform(0, 6)
        self.carry = 0
        self.dt = 0.0
        self.lucky = False
        self.hidden = False
        self.busy = False      # on a delivery job
        self.held = None       # (x, y) of a block on its way into the wall
        self.poles = 0         # ladder sections being carried
        self.leaving = False   # walking off because the crew got smaller
        self.gone = False
        self.gen = self.job_idle()

    def reset(self, x):
        """Drop whatever was going on and stand at x on the ground."""
        self.x, self.y, self.level = x, self.w.ground, 0
        self.carry = self.poles = 0
        self.held = None
        self.busy = self.hidden = False
        self.gen = self.job_idle()

    # ---- frame update ----
    def tick(self, dt):
        self.dt = dt
        try:
            next(self.gen)
        except StopIteration:
            self.busy = False
            self.gen = self.job_idle()
            next(self.gen)

    def assign(self, gen, busy=False):
        floor = self.w.level_y(self.level)
        if abs(self.y - floor) > .5:  # caught halfway down a ladder: step back onto the floor first
            gen = self._then(self.climb_to(floor), gen)
        self.gen = gen
        self.busy = busy

    @staticmethod
    def _then(first, second):
        yield from first
        yield from second

    # ---- primitive moves ----
    def walk_to(self, x, speed=None):
        while True:
            d = x - self.x
            v = speed or (CARRY_WALK if self.carry else WALK)
            step = v * self.dt
            if abs(d) <= step:
                self.x = x
                return
            self.f = 1 if d > 0 else -1
            self.x += step * self.f
            self.pose = "carry" if self.carry else ("run" if v >= RUN else "walk")
            self.ph += step * (0.42 if v < RUN else 0.3)
            yield

    def climb_to(self, y):
        while True:
            d = y - self.y
            step = CLIMB * self.dt
            if abs(d) <= step:
                self.y = y
                return
            self.y += step if d > 0 else -step
            self.pose = "climb"
            self.ph += step * 0.9
            yield

    def pause(self, secs, pose="stand"):
        t = 0.0
        while t < secs:
            self.pose = pose
            self.ph += self.dt * 3
            t += self.dt
            yield

    def stroll(self, x, side):
        """Walk along the current level: planks are always safe, the floor between
        them only once it is finished."""
        w = self.w
        if self.level and not w.floor_done(self.level):
            spans = [w.walkway(s, self.level) for s in (0, 1) if w.scaffold.progress[s][self.level] >= 1]
            here = next(((lo, hi) for lo, hi in spans if lo - 1 <= self.x <= hi + 1), None)
            if here and not here[0] - 1 <= x <= here[1] + 1:
                yield from self.walk_to(max(here[0], min(here[1], x)))  # to the end of this plank
                while not w.floor_done(self.level):
                    self.pose = "stand"
                    yield
        yield from self.walk_to(x)

    def go(self, x, level, side):
        w = self.w
        while self.level < level:
            yield from self.stroll(w.ladder_x(side, self.level + 1), side)
            while not w.scaffold.ready(side, self.level + 1):  # not put up yet: wait for it
                self.pose = "stand"
                yield
            yield from self.climb_to(w.level_y(self.level + 1))
            self.level += 1
        while self.level > level:
            yield from self.stroll(w.ladder_x(side, self.level), side)
            yield from self.climb_to(w.level_y(self.level - 1))
            self.level -= 1
        yield from self.stroll(x, side)

    # ---- jobs ----
    def job_deliver(self, bricks, side, landing=None):
        w, rng = self.w, self.rng
        pile = w.piles[side]
        if landing is None:
            yield from self.go(pile + rng.uniform(-3, 3), 0, side)
            self.f = 1 if side == 0 else -1
            here = side
            while not w.take_from_pile(here, len(bricks)):  # pallet empty: wait for the truck...
                other = 1 - here
                coming = any(t.side == here and t.blocks and not t.done for t in w.trucks)
                if not coming and w.pile_left[other] >= len(bricks):  # ...or use the other one
                    here = other
                    yield from self.walk_to(w.piles[here] + rng.uniform(-3, 3))
                    continue
                self.pose = "stand"
                yield
        else:  # the crane has lifted blocks onto a landing at this floor
            cr = w.crane
            yield from self.go(cr.landing_x(landing) + rng.uniform(-4, 4), landing, cr.side)
            while not cr.take(landing, len(bricks)):
                self.pose = "stand"
                yield
        yield from self.pause(0.9, "bend")
        self.carry = len(bricks)
        for b in bricks:
            bx = w.ox + b.cx
            yield from self.go(w.stand_x(b, side), w.brick_level(b), side)
            while not w.supported(b):  # never set a block on thin air
                self.pose = "stand"
                yield
            self.f = 1 if bx > self.x else -1
            by = w.oy + b.cy
            t = 0.0
            while t < 0.7:
                k = t / 0.7
                self.held = (self.x + 3 * self.f + (bx - self.x - 3 * self.f) * k, self.y - 11 + (by - self.y + 11) * k)
                self.pose = "place"
                t += self.dt
                yield
            self.held = None
            w.place(b)
            self.carry -= 1
        self.carry = 0
        if landing is not None:
            return  # stay up on the working floor for the next load
        yield from self.go(pile + (-1 if side == 0 else 1) * rng.uniform(8, 30), 0, side)

    def job_scaffold(self, side, levels):
        """Carry ladder sections up and raise them one level after another."""
        w = self.w
        yield from self.go(w.racks[side] + self.rng.uniform(-6, 6), 0, side)
        yield from self.pause(0.8, "bend")
        self.poles = len(levels)
        for lv in levels:
            yield from self.go(w.ladder_x(side, lv), lv - 1, side)
            while not w.floor_done(lv - 1):  # the ladder needs a finished floor to stand on
                self.pose = "stand"
                yield
            self.f = 1 if side == 1 else -1
            t = 0.0
            while t < INSTALL_TIME:
                w.scaffold.set(side, lv, t / INSTALL_TIME)
                self.pose = "place"
                t += self.dt
                yield
            w.scaffold.set(side, lv, 1.0)
            self.poles -= 1
        yield from self.go(w.racks[side] + (-1 if side == 0 else 1) * self.rng.uniform(10, 30), 0, side)
        w.scaffold.crews[side] -= 1

    def job_dismantle(self, side, levels):
        """Take the top sections down, highest first, and carry them back to the rack."""
        w = self.w
        for lv in levels:
            yield from self.go(w.ladder_x(side, lv), lv - 1, side)
            self.f = 1 if side == 1 else -1
            t = 0.0
            while t < INSTALL_TIME:
                w.scaffold.set(side, lv, 1 - t / INSTALL_TIME)
                self.pose = "place"
                t += self.dt
                yield
            w.scaffold.set(side, lv, 0.0)
            self.poles += 1
        yield from self.go(w.racks[side], 0, side)
        yield from self.pause(0.8, "bend")
        w.scaffold.rack[side] += self.poles
        self.poles = 0
        w.scaffold.crews[side] -= 1

    def job_idle(self):
        w, rng = self.w, self.rng
        if self.level:
            cr = w.crane
            if cr and cr.present and w.phase == "build" and not ((w.night or w.storm()) and w.night_shift()):
                yield from self.pause(rng.uniform(3, 6), "stand")  # wait up here for the next load
            yield from self.go(self.x, 0, 0 if self.x < w.center else 1)
        r = rng.random()
        if w.storm() and w.night_shift():  # thunderstorm: wait it out by the container
            yield from self.walk_to(w.rest_x + rng.uniform(-26, 26))
            self.f = rng.choice((-1, 1))
            yield from self.pause(rng.uniform(5, 12), "talk" if r < .5 else "stand")
            yield
            return
        if w.night and w.fire_level > .3:  # evening by the campfire: sit, chat, dance
            side = rng.choice((-1, 1))
            yield from self.walk_to(w.fire_x + side * rng.uniform(13, 48))
            self.f = 1 if w.fire_x > self.x else -1
            pose = "sit" if r < .45 else "talk" if r < .75 else "dance"
            yield from self.pause(rng.uniform(8, 25), pose)
            yield
            return
        if w.phase == "admire" and r < .3:
            self.f = 1 if w.center > self.x else -1
            yield from self.pause(rng.uniform(2, 4), "cheer")
        elif r < .35:
            yield from self.walk_to(w.rest_x + rng.uniform(-24, 24))
            self.f = rng.choice((-1, 1))
            yield from self.pause(rng.uniform(15, 60), "sit")
        elif r < .6:
            yield from self.walk_to(rng.uniform(w.site[0] - 70, w.site[1] + 70))
            yield from self.pause(rng.uniform(3, 9))
        elif r < .85:
            others = [o for o in w.workers if o is not self and not o.busy and not o.hidden]
            if others:
                o = rng.choice(others)
                yield from self.walk_to(o.x + rng.choice((-7, 7)))
                self.f = 1 if o.x > self.x else -1
                yield from self.pause(rng.uniform(6, 15), "talk")
        else:
            self.f = 1 if w.center > self.x else -1
            yield from self.pause(rng.uniform(4, 10))
        yield

    def job_panic(self, away):
        self.held = None
        self.poles = 0
        vy = 0.0
        while self.y < self.w.ground:
            vy += 300 * self.dt
            self.y = min(self.w.ground, self.y + vy * self.dt)
            self.pose = "climb"
            yield
        self.level = 0
        self.carry = 0
        yield from self.walk_to(-15 if away < 0 else self.w.W + 15, RUN * (1.25 if self.lucky else 1))
        self.hidden = True
        while True:
            yield

    def job_leave(self):
        self.leaving = True
        yield from self.walk_to(-15 if self.x < self.w.W / 2 else self.w.W + 15)
        self.gone = True
        yield

    def job_return(self, x):
        self.hidden = False
        yield from self.walk_to(x)
