"""The construction crew: how a worker is drawn, and what each one does.

Behaviour is written as generators: each job yields once per frame and reads
the frame time from self.dt, so a job reads like a to-do list
(walk to the pallet, pick up blocks, climb, place each block, come back down).
"""

import math

from .site import INSTALL_TIME, draw_ladder

WALK, CARRY_WALK, CLIMB, RUN = 20.0, 15.0, 10.0, 46.0
THIGH, SHIN, TORSO, UPPER, FORE = 4.6, 4.4, 6.2, 3.4, 3.2
SEAT_H = 3.2   # height of a log or crate to sit on
SEATED = ("sit", "sit_talk", "sit_drink", "sit_clap", "guitar")
# poses that leave a hand free for an umbrella
UMBRELLA_POSES = ("walk", "stand", "talk", "drink", "warm", "cheer", "dance", "dance2",
                  "sit", "sit_talk", "sit_drink", "float")


def _seg(x, y, angle, length, f):
    """End of a limb hanging at `angle` from straight down (positive = forward)."""
    return x + math.sin(angle) * length * f, y + math.cos(angle) * length


def draw_person(cr, x, y, f, pose, ph, carry=0, rot=0.0, lift=0.0, poles=0, umbrella=0.0, wind=0.0):
    """Silhouette worker with a hard hat; (x, y) are the feet, f the facing.
    umbrella: how far an umbrella held overhead is open (0 = none)."""
    if pose == "lie":  # asleep on the ground, head towards f, face up
        cr.save()
        cr.translate(x - f * 8, y - 1.7)
        cr.rotate(f * math.pi / 2)
        draw_person(cr, 0, 0, -f, "lying", ph)
        cr.restore()
        return
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
    elif pose in SEATED:
        legs = [(1.57, .2), (1.5, .3)]
        lean = -.05
        if pose == "sit_talk":
            g = .7 + .4 * math.sin(ph * .7)
            arms = [(g, g + .9), (.5, 1.1)]
        elif pose == "sit_drink":
            arms = [(1.9, 4.0) if math.sin(ph * .45) > .55 else (.6, 1.7), (.4, 1.0)]
        elif pose == "sit_clap":
            a = .22 * abs(math.sin(ph * 2.2))
            arms = [(1.0 + a, 2.1 + a), (1.0 - a, 2.1 - a)]
        elif pose == "guitar":
            arms = [(1.45, 1.81), (0.0, 1.7 + .25 * math.sin(ph * 4))]  # fretting hand, strumming hand
            lean = .04
        else:
            arms = [(.5, 1.1), (.4, 1.0)]
    elif pose == "talk":
        g = .4 + .3 * math.sin(ph * .7)
        legs = [(.08, 0), (-.08, 0)]
        arms = [(g, g + .9), (.1, .2)]
    elif pose == "dance":
        kick = max(0, s)
        legs = [(.9 * kick, -.9 * kick), (-.15 * max(0, -s), 0)]
        arms = [(math.pi - .7 + .5 * s, math.pi - .2 + .4 * c), (math.pi - .7 - .5 * s, math.pi - .2 - .4 * c)]
        lean = .1 * c
    elif pose == "dance2":  # hips sway, both arms up waving
        legs = [(.22 * s, -.1 * max(0, s)), (-.22 * s, -.1 * max(0, -s))]
        arms = [(math.pi - 1.0 + .4 * s, math.pi - .6 + .5 * s), (-(math.pi - 1.0) + .4 * s, -(math.pi - .6) + .5 * s)]
        lean = .1 * s
    elif pose == "clap":
        a = .22 * abs(math.sin(ph * 2.2))
        legs = [(.08, 0), (-.08, 0)]
        arms = [(1.0 + a, 2.1 + a), (1.0 - a, 2.1 - a)]
    elif pose == "warm":  # hands held out to the fire
        legs = [(.1, 0), (-.06, 0)]
        arms = [(1.05, 1.35), (.95, 1.25)]
        lean = .1
    elif pose == "stretch":
        legs = [(.04, 0), (-.04, 0)]
        arms = [(math.pi - .12, math.pi - .1), (math.pi - .3, math.pi - .25)]
        lean = -.1
    elif pose == "drink":
        legs = [(.06, 0), (-.06, 0)]
        arms = [(1.9, 4.0), (.1, .2)]
    elif pose == "cheer":
        legs = [(.15, 0), (-.15, 0)]
        arms = [(math.pi - .5 + .2 * s, math.pi - .3), (math.pi - .5 - .2 * s, math.pi - .3)]
    elif pose == "tumble":
        legs = [(.9 + s, .4), (-.6 - s, -.2)]
        arms = [(2.2 + c, 2.6), (-2.0 - c, -2.4)]
    elif pose == "float":  # hanging from an umbrella, legs dangling
        legs = [(.3 + .15 * s, .15), (-.2 - .15 * s, -.05)]
        arms = [(2.7, 3.0), (.7 + .3 * s, 1.1 + .3 * s)]
    elif pose == "lying":
        legs = [(.03, 0), (-.03, 0)]
        arms = [(.1, .15), (-.05, .05)]
    else:  # stand
        legs = [(.06, 0), (-.06, 0)]
        arms = [(.12, .2), (-.05, .05)]

    if umbrella > .02:  # the front hand holds the umbrella up
        arms = [(2.75, 3.05)] + list(arms[1:])
    # place the hip so the lowest foot touches y (or, seated, on a seat SEAT_H high)
    drops = [math.cos(t) * THIGH + math.cos(k) * SHIN for t, k in legs]
    hip_y = y - max(drops) if pose not in SEATED else y - SEAT_H
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
    if pose == "guitar":
        gx, gy = hip_x + 3.2 * f, hip_y - 2.6
        cr.save()
        cr.translate(gx, gy)
        cr.scale(3.0, 2.4)
        cr.arc(0, 0, 1, 0, math.tau)
        cr.restore()
        cr.fill()
        cr.set_line_width(.9)
        cr.move_to(gx, gy)
        cr.line_to(hip_x + 9.6 * f, hip_y - 9.1)
        cr.stroke()
        cr.set_line_width(1.5)
        cr.move_to(hip_x + 9.4 * f, hip_y - 8.9)
        cr.line_to(hip_x + 10.4 * f, hip_y - 10.0)
        cr.stroke()
    if umbrella > .02:
        draw_umbrella(cr, hands[0][0], hands[0][1], umbrella, wind)
    if pose in ("drink", "sit_drink"):  # a mug in the drinking hand
        cr.rectangle(hands[0][0] - .7, hands[0][1] - 1.2, 1.4, 1.6)
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


def draw_umbrella(cr, hx, hy, k, wind):
    """Shaft up from the hand, canopy opening with k, leaning into the wind."""
    lean = -.35 * wind
    tx, ty = hx + math.sin(lean) * 8.5, hy - math.cos(lean) * 8.5
    cr.set_line_width(.8)
    cr.move_to(hx, hy + 1)
    cr.line_to(tx, ty - 1.2)
    cr.stroke()
    cr.save()
    cr.translate(tx, ty)
    cr.rotate(lean)
    half = 1.2 + 6.3 * k
    cr.move_to(-half, 0)  # a dome with a scalloped rim
    cr.curve_to(-half, -3.6 * k - .6, half, -3.6 * k - .6, half, 0)
    n = 4
    for i in range(n, 0, -1):
        x0 = -half + 2 * half * i / n
        x1 = -half + 2 * half * (i - 1) / n
        cr.curve_to(x0 - .25 * (x0 - x1), -.9 * k, x1 + .25 * (x0 - x1), -.9 * k, x1, 0)
    cr.close_path()
    cr.fill()
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
        self.has_umbrella = rng.random() < .55
        self.umbrella = 0.0    # how far it's open
        self.gliding = False   # jumped off the building holding it
        self.poles = 0         # ladder sections being carried
        self.leaving = False   # walking off because the crew got smaller
        self.gone = False
        self.dancer = rng.choice((0, 1, 2))  # 0: rather clap; 1, 2: two dance styles
        self.gen = self.job_idle()

    def reset(self, x):
        """Drop whatever was going on and stand at x on the ground."""
        self.x, self.y, self.level = x, self.w.ground, 0
        self.carry = self.poles = 0
        self.held = None
        self.busy = self.hidden = self.gliding = False
        self.gen = self.job_idle()

    # ---- frame update ----
    def tick(self, dt):
        self.dt = dt
        want = self.gliding or (self.has_umbrella and self.w.raining() and not self.carry and not self.poles
                                and self.pose in UMBRELLA_POSES)
        self.umbrella = max(0.0, min(1.0, self.umbrella + (2.5 if want else -3.0) * min(dt, .1)))
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

    def pause(self, secs, pose="stand", until=None):
        """Hold a pose for secs, or until `until()` says to stop."""
        t = 0.0
        while t < secs and not (until and until()):
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
        if w.storm() and w.night_shift():  # thunderstorm: wait it out by the container
            yield from self.job_shelter()
            return
        if w.campfire_on():  # evening: a seat by the fire for the whole night
            yield from self.job_evening()
            return
        r = rng.random()
        if w.phase == "admire" and r < .3:
            self.f = 1 if w.center > self.x else -1
            yield from self.pause(rng.uniform(2, 4), "cheer")
        elif r < .35:
            seat = w.claim_seat(self, w.rest_seats)
            if seat is not None:  # a break on a crate by the container
                try:
                    yield from self.walk_to(seat)
                    self.f = rng.choice((-1, 1))
                    yield from self.pause(rng.uniform(15, 60), rng.choice(("sit", "sit", "sit_drink", "sit_talk")))
                finally:
                    w.release_seat(self)
            else:
                yield from self.walk_to(w.rest_x + rng.uniform(-30, 30) * w.u)
                yield from self.pause(rng.uniform(8, 20), "drink")
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

    def job_shelter(self):
        """Stand by the container until the storm passes (no pacing about)."""
        w, rng = self.w, self.rng
        yield from self.walk_to(w.rest_x + rng.uniform(-26, 26) * w.u)
        self.f = rng.choice((-1, 1))
        over = lambda: not (w.storm() and w.night_shift())
        while not over():
            yield from self.pause(rng.uniform(10, 30), rng.choice(("stand", "talk", "drink")), until=over)
        yield

    # ---- evenings by the campfire ----
    def face_fire(self):
        self.f = 1 if self.w.fire_x > self.x else -1

    def job_evening(self):
        """Take a seat by the fire once, then spend the night around it: talk, drink,
        play the guitar, dance to it, stoke the fire, doze off. Nobody wanders in
        circles: each worker keeps their own spot until dawn."""
        w, rng = self.w, self.rng
        seat = w.claim_seat(self, w.camp_seats)
        home = seat if seat is not None else w.camp_standing_spot(self)
        over = lambda: not w.campfire_on()
        try:
            yield from self.walk_to(home)
            self.face_fire()
            while not over():
                yield from self.evening_turn(home, seat is not None, over)
                if self.x != home and not over():
                    yield from self.walk_to(home)
                    self.face_fire()
        finally:
            w.release_seat(self)
            if w.guitarist is self:
                w.guitarist = None
            if w.stoker is self:
                w.stoker = None
        yield

    def evening_turn(self, home, seated, over):
        w, rng = self.w, self.rng
        music = w.guitarist is not None and w.guitarist is not self
        sit = (lambda p: p) if seated else (lambda p: {"sit": "stand", "sit_talk": "talk", "sit_drink": "drink",
                                                         "sit_clap": "clap"}.get(p, "stand"))
        if w.late_night() and rng.random() < .12:
            yield from self.evening_sleep(home, over)
            return
        options = [("rest", 3), ("talk", 3), ("drink", 1.5), ("warm", 1.2), ("stretch", .6), ("visit", 1)]
        if seated and w.guitarist is None:
            options.append(("guitar", 2.5))
        if music:
            options += [("dance", 4 if self.dancer else 1.2), ("clap", 3)]
        if w.stoker is None and w.fire_level > .5:
            options.append(("stoke", .7))
        total = sum(k for _, k in options)
        r = rng.uniform(0, total)
        for act, k in options:
            r -= k
            if r <= 0:
                break
        self.face_fire()
        if act == "rest":
            yield from self.pause(rng.uniform(20, 80), sit("sit"), until=over)
        elif act == "talk":
            yield from self.pause(rng.uniform(15, 50), sit("sit_talk"), until=over)
        elif act == "drink":
            yield from self.pause(rng.uniform(10, 25), sit("sit_drink"), until=over)
        elif act == "clap":
            yield from self.pause(rng.uniform(10, 30), sit("sit_clap"), until=lambda: over() or w.guitarist is None)
        elif act == "guitar":
            w.guitarist = self
            try:
                yield from self.pause(rng.uniform(70, 220), "guitar", until=over)
            finally:
                if w.guitarist is self:
                    w.guitarist = None
            yield from self.pause(rng.uniform(10, 30), "sit_drink", until=over)
        elif act == "dance":  # get up in front of the seat and dance while the music lasts
            spot = home + (6 if w.fire_x > home else -6) * w.u
            yield from self.walk_to(spot)
            self.face_fire()
            style = "dance2" if self.dancer == 2 else "dance"
            stop = lambda: over() or w.guitarist is None
            t_end = rng.uniform(15, 45)
            while t_end > 0 and not stop():
                d = rng.uniform(2.5, 6)
                if rng.random() < .3:  # a little shuffle to one side and back
                    yield from self.walk_to(spot + rng.uniform(-4, 4) * w.u, speed=WALK * .4)
                    self.f = rng.choice((-1, 1))
                yield from self.pause(d, style, until=stop)
                t_end -= d
        elif act == "warm":
            spot = home + (5 if w.fire_x > home else -5) * w.u
            yield from self.walk_to(spot)
            self.face_fire()
            yield from self.pause(rng.uniform(10, 25), "warm", until=over)
        elif act == "stretch":
            yield from self.pause(rng.uniform(2, 3.5), "stretch", until=over)
        elif act == "stoke":  # throw another log on
            w.stoker = self
            try:
                side = 1 if self.x > w.fire_x else -1
                yield from self.walk_to(w.fire_x + side * 10 * w.u)
                self.face_fire()
                yield from self.pause(1.4, "bend", until=over)
                w.stoke()
                yield from self.pause(rng.uniform(3, 8), "warm", until=over)
            finally:
                if w.stoker is self:
                    w.stoker = None
        elif act == "visit":  # stroll over to someone else's seat for a chat
            others = [o for o in w.workers if o is not self and w.seat_of(o) is not None and not o.busy]
            if not others:
                return
            o = rng.choice(others)
            side = 1 if o.x < w.fire_x else -1
            yield from self.walk_to(o.x + side * 6 * w.u)
            self.f = 1 if o.x > self.x else -1
            yield from self.pause(rng.uniform(12, 35), "talk", until=over)

    def evening_sleep(self, home, over):
        """Late at night: doze off by the fire, or turn in at the container."""
        w, rng = self.w, self.rng
        if rng.random() < .5:  # lie down just behind the seat, head away from the fire
            away = -1 if w.fire_x > home else 1
            yield from self.walk_to(home + away * 13 * w.u)
            self.f = away
            yield from self.pause(rng.uniform(240, 900), "lie", until=over)
            yield from self.pause(rng.uniform(2, 3), "stretch")
            return
        yield from self.walk_to(w.rest_x)  # the seat stays theirs while they sleep
        self.hidden = True  # inside the container
        try:
            t = rng.uniform(600, 2400)
            while t > 0 and not over():
                t -= self.dt
                self.pose = "stand"
                yield
        finally:
            self.hidden = False
        yield from self.pause(rng.uniform(2, 3), "stretch")

    def job_glide(self, away):
        """Daytime, up on the building, umbrella in hand: open it and jump."""
        w = self.w
        self.held = None
        self.carry = self.poles = 0
        self.gliding = True
        self.f = away
        yield from self.pause(w.rng.uniform(.3, 1.0), "stand")  # a moment's hesitation
        vx, vy = away * w.rng.uniform(22, 34), -w.rng.uniform(25, 40)  # the leap
        sway = w.rng.uniform(0, 6)
        while self.y < w.ground:
            vy = min(vy + 260 * self.dt, 20.0)  # the umbrella catches the air
            drift = w.wxe["wind"] * 25 + math.sin(self.ph * .7 + sway) * 6
            vx += (drift - vx) * min(1.0, self.dt * 1.5)
            self.x += vx * self.dt
            self.y = min(w.ground, self.y + vy * self.dt)
            self.pose = "float"
            self.ph += self.dt * 4
            yield
        self.gliding = False
        self.level = 0
        yield from self.walk_to(-15 if away < 0 else w.W + 15, RUN * (1.25 if self.lucky else 1))
        self.hidden = True
        while True:
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
        self.hidden = self.gliding = False
        yield from self.walk_to(x)
