"""Construction-site logistics: the scaffold the crew puts up and takes down,
and the truck that brings blocks and scaffold sections to the pallets."""

import math


def draw_ladder(cr, x0, y0, x1, y1, width):
    """A ladder from (x0, y0) to (x1, y1): two rails and rungs every ~3 px."""
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln * width / 2, dx / ln * width / 2
    cr.set_line_width(0.8)
    for sgn in (-1, 1):
        cr.move_to(x0 + sgn * nx, y0 + sgn * ny)
        cr.line_to(x1 + sgn * nx, y1 + sgn * ny)
    for i in range(1, int(ln / 3)):
        k = i * 3 / ln
        cx, cy = x0 + dx * k, y0 + dy * k
        cr.move_to(cx - nx, cy - ny)
        cr.line_to(cx + nx, cy + ny)
    cr.stroke()


def draw_lattice(cr, x0, y0, x1, y1, width):
    """A steel lattice girder (crane mast or jib) from (x0, y0) to (x1, y1)."""
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln * width / 2, dx / ln * width / 2
    cr.set_line_width(max(.7, width * .16))
    for sgn in (-1, 1):
        cr.move_to(x0 + sgn * nx, y0 + sgn * ny)
        cr.line_to(x1 + sgn * nx, y1 + sgn * ny)
    n = max(1, int(ln / width))
    for i in range(n):
        a, b = i / n, (i + 1) / n
        sgn = 1 if i % 2 else -1
        cr.move_to(x0 + dx * a + sgn * nx, y0 + dy * a + sgn * ny)
        cr.line_to(x0 + dx * b - sgn * nx, y0 + dy * b - sgn * ny)
    cr.stroke()


INSTALL_TIME = 1.6  # seconds to raise (or take down) one ladder section


class Scaffold:
    """One ladder section per side and level. progress[side][lv] goes 0..1 while
    a worker raises it; a level is usable once it and everything below it is up."""

    def __init__(self, world):
        self.w = world
        n = world.levels + 2
        self.progress = [[0.0] * n for _ in range(2)]
        self.built = [0, 0]       # highest level reachable on each side
        self.reserved = [0, 0]    # highest level promised to a scaffolder
        self.crews = [0, 0]       # scaffolders currently working each side
        self.rack = [0, 0]        # sections lying on the rack by the pallet
        self.undelivered = [world.levels, world.levels]

    def ready(self, side, lv):
        return lv <= self.built[side]

    def set(self, side, lv, k):
        self.progress[side][lv] = max(0.0, min(1.0, k))
        b = 0
        while b + 1 <= self.w.levels and self.progress[side][b + 1] >= 1:
            b += 1
        self.built[side] = b

    def complete_to(self, lv):
        """Instantly stand up to `lv` (work done while the wallpaper wasn't running)."""
        lv = min(lv, self.w.levels)
        for side in (0, 1):
            for k in range(1, lv + 1):
                self.progress[side][k] = 1.0
            self.built[side] = self.reserved[side] = lv
            self.undelivered[side] = self.w.levels - lv

    def knock(self, side, lv, abduct=False):
        """Section lv falls, taking everything above it on that side with it (or, in
        a tractor beam, just that section is carried off)."""
        w = self.w
        for k in range(lv, (lv + 1) if abduct else (w.levels + 1)):
            if self.progress[side][k] > 0:
                self.progress[side][k] = 0.0
                x, y = w.ladder_x(side, k), w.level_y(k) + w.lift / 2
                for _ in range(2):
                    if abduct:
                        w.add_particle(x, y, 0, 0, "pole", abduct=True)
                    else:
                        w.add_particle(x, y, w.rng.uniform(-60, 60) * w.u, -w.rng.uniform(20, 120) * w.u, "pole")
        self.set(side, 1, self.progress[side][1])

    def sections(self):
        for side in (0, 1):
            for lv in range(1, self.w.levels + 1):
                if self.progress[side][lv] > 0:
                    yield side, lv

    def draw(self, cr):
        w, u = self.w, self.w.u
        cr.set_line_width(1 * u)
        for side, lv in self.sections():
            k = self.progress[side][lv]
            x = w.ladders[side][lv]
            y0 = w.level_y(lv - 1)
            y1 = y0 - (w.lift + 3 * u) * k
            for rx in (x - 2.2 * u, x + 2.2 * u):
                cr.move_to(rx, y0)
                cr.line_to(rx, y1)
            r = y0 - 3 * u
            while r > y1:
                cr.move_to(x - 2.2 * u, r)
                cr.line_to(x + 2.2 * u, r)
                r -= 3.5 * u
            if k >= 1:  # walkway from past the ladders to the wall at this level...
                y = w.level_y(lv)
                lo, hi = w.walkway(side, lv)
                wall_end = hi if side == 0 else lo
                # ...once there's stone under its far end to rest on; until then
                # just a landing at the top of the ladder
                if not w.solid_near(wall_end + (2 if side == 0 else -2) * u, y + 3 * u, 3 * u):
                    lad = w.ladder_x(side, lv)
                    lo, hi = (lo, min(hi, lad + 8 * u)) if side == 0 else (max(lo, lad - 8 * u), hi)
                cr.move_to(lo, y)
                cr.line_to(hi, y)
        cr.stroke()
        # planks bridging openings (arches, colonnades) at every level that's up, once
        # the stone on both sides is there to rest them on
        cr.set_line_width(1.6 * u)
        for lv in range(1, max(self.built) + 1):
            y = w.level_y(lv)
            for x0, x1 in w.deck_gaps[lv]:
                if w.solid_near(x0 - 2 * u, y + 2 * u, 2.5 * u) and w.solid_near(x1 + 2 * u, y + 2 * u, 2.5 * u):
                    cr.move_to(x0, y)
                    cr.line_to(x1, y)
        cr.stroke()

    def draw_racks(self, cr):
        w, u = self.w, self.w.u
        for side in (0, 1):
            x = w.racks[side]
            for i in range(min(self.rack[side], 8)):
                y = w.ground - 1.5 * u - i * 3 * u
                draw_ladder(cr, x - 11 * u, y, x + 11 * u, y, 2.4 * u)


class Truck:
    """A flatbed that drives in from its side of the screen, unloads at the
    pallet, and backs out again. On the yard's side it starts from the stockyard
    instead: loads up there, and backs into its bay again afterwards."""

    SPEED = 70.0
    UNLOAD = 3.0
    LOAD = 4.0

    def __init__(self, world, side, blocks, poles, crane=None, parked=False):
        self.w = world
        self.side = side
        self.blocks, self.poles = blocks, poles
        self.crane = crane          # "in": brings the folded crane, "out": comes to take it away
        self.carrying_crane = crane == "in"
        self.load0 = max(1, blocks)
        u = world.u
        self.length = 66 * u
        self.dir = 1 if side == 0 else -1          # facing direction
        self.x = -self.length - 10 * u if side == 0 else world.W + self.length + 10 * u  # front bumper
        self.bay = world.depot_bay(self.length) if side == world.yard_side else None
        self.state, self.t = "in", 0.0
        if self.bay is not None:
            self.x = self.bay
            self.state = "parked" if parked else "load"
        if not parked:
            pile = world.crane.x if crane else world.piles[side]
            self.stop = pile - 12 * u if side == 0 else pile + 12 * u
        self.done = False
        self.wheel = 0.0

    def update(self, dt):
        w, u = self.w, self.w.u
        v = self.SPEED * u * dt
        if self.state == "load":  # loading up at the stockyard
            self.t += dt
            if self.t >= self.LOAD:
                self.state, self.t = "in", 0.0
        elif self.state == "in":
            d = self.stop - self.x
            if abs(d) <= v:
                self.x = self.stop
                self.state = "unload"
            else:
                self.x += v * (1 if d > 0 else -1)
                self.wheel += v
        elif self.state == "unload":
            self.t += dt
            k = min(1.0, dt / self.UNLOAD * 1.2)
            moved = min(self.blocks, math.ceil(self.load0 * k))
            self.blocks -= moved
            w.pile_left[self.side] += moved
            if self.poles and self.t > self.UNLOAD * .5:
                w.scaffold.rack[self.side] += self.poles
                w.scaffold.undelivered[self.side] -= self.poles
                self.poles = 0
            if self.crane and self.t > self.UNLOAD * .5:
                if self.crane == "in" and self.carrying_crane:
                    self.carrying_crane = False
                    w.crane.arrive()
                elif self.crane == "out" and not self.carrying_crane and w.crane.ready_to_go():
                    self.carrying_crane = True
                    w.crane.depart()
            waiting = self.crane == "out" and not self.carrying_crane
            if self.t >= self.UNLOAD and not self.blocks and not waiting:
                self.state = "out"
        else:
            self.x -= self.dir * v * 1.3
            self.wheel -= v
            if self.bay is not None and (self.x - self.bay) * self.dir <= 0:
                self.done = True  # back in its bay (the parked truck takes over)
            if self.x < -self.length - 20 * u or self.x > w.W + self.length + 20 * u:
                self.done = True

    def leave(self):
        self.state = "out"

    def draw(self, cr):
        u, g, f = self.w.u, self.w.ground, self.dir
        front = self.x
        back = front - f * self.length

        def rect(xa, xb, y0, y1):
            cr.rectangle(min(xa, xb), y0, abs(xb - xa), y1 - y0)

        rect(front, front - f * 17 * u, g - 22 * u, g - 6 * u)          # cab
        rect(front - f * 17 * u, back, g - 11 * u, g - 6 * u)           # flatbed
        rect(front - f * 18 * u, front - f * 20 * u, g - 16 * u, g - 11 * u)
        cr.fill()
        for wx in (front - f * 9 * u, back + f * 10 * u, back + f * 20 * u):
            cr.arc(wx, g - 5 * u, 5 * u, 0, math.tau)
            cr.fill()
        rows = min(3, 1 + self.blocks * 3 // self.load0) if self.blocks else 0
        if self.state == "load":  # the load goes on a row at a time
            rows = min(rows, int(self.t / self.LOAD * (rows + 1)))
        if self.blocks:
            for r in range(rows):
                for i in range(6):
                    bx = back + f * (4 + i * 6.6) * u
                    cr.rectangle(min(bx, bx + f * 5.6 * u), g - 11 * u - (r + 1) * 4.6 * u, 5.6 * u, 4 * u)
            cr.fill()
        if self.carrying_crane:  # folded lattice sections on the bed
            for i in range(2):
                y = g - 13 * u - i * 5 * u
                draw_lattice(cr, back + f * 3 * u, y, front - f * 19 * u, y, 4 * u)
        if self.poles:
            for i in range(min(self.poles, 4)):
                y = g - 12.5 * u - i * 3 * u - rows * 4.6 * u  # resting on the load
                draw_ladder(cr, back, y, front - f * 18 * u, y, 2.4 * u)
        cr.save()  # windscreen
        cr.set_operator(0)  # CLEAR: let the sky show through
        rect(front - f * 2 * u, front - f * 9 * u, g - 20 * u, g - 14 * u)
        cr.fill()
        cr.restore()


class Crane:
    """A tower crane for tall monuments. A truck brings it; it climbs as the
    building rises, lifts blocks from the ground pallet to a landing on the
    walkway at the working floor, and leaves on a truck once the work is done."""

    LOAD = 6

    def __init__(self, world, side):
        self.w = world
        u = world.u
        self.side = side
        sgn = -1 if side == 0 else 1
        self.x = max(18 * u, min(world.W - 18 * u, world.piles[side] + sgn * 36 * u))
        self.present = False
        self.leaving = False
        self.gone = False
        self.sections = 0.0
        self.state, self.t = "idle", 0.0
        self.trolley = world.piles[side]
        self.hook = 0.0                 # rope length below the jib
        self.load = 0
        self.target = None              # landing level being served
        self.landings = {}              # level -> blocks lying on the landing pallet
        self.reserved = {}              # level -> blocks promised to workers

    # ---- arrival and departure (driven by trucks) ----
    def arrive(self):
        self.present, self.sections = True, 1.0

    def ready_to_go(self):
        return self.sections <= 1.01 and self.load == 0 and self.state == "idle"

    def depart(self):
        self.present, self.gone = False, True

    def mast_top(self):
        return self.w.ground - self.sections * self.w.lift - 8 * self.w.u

    def wanted_sections(self):
        w = self.w
        if self.leaving or w.phase != "build":
            return 1.0
        return float(min(w.levels + 4, max(4, w.top_level + 6)))

    def landing_x(self, lv):
        lo, hi = self.w.walkway(self.side, lv)
        return (lo + hi) / 2

    def landing_level(self):
        """Blocks go to the floor the crew is working on, once its walkway is up."""
        w = self.w
        lv = min(w.lowest_open, w.levels)
        if lv < 3 or w.scaffold.built[self.side] < lv:
            return None
        return lv

    def available(self, lv):
        return self.landings.get(lv, 0) - self.reserved.get(lv, 0)

    def stocked_landing(self, k, near):
        """A landing with k blocks to spare, preferring the one closest to level `near`."""
        levels = [lv for lv in self.landings if self.available(lv) >= k]
        return min(levels, key=lambda lv: abs(lv - near)) if levels else None

    def reserve(self, lv, k):
        self.reserved[lv] = self.reserved.get(lv, 0) + k

    def take(self, lv, k):
        if self.landings.get(lv, 0) < k:
            return False
        self.landings[lv] -= k
        self.reserved[lv] = max(0, self.reserved.get(lv, 0) - k)
        return True

    def jib_end(self):
        """The jib reaches over the pallet and the furthest landing it serves."""
        sgn = -1 if self.side == 0 else 1
        reach = [self.w.piles[self.side]] + [self.landing_x(lv) for lv in self.landings]
        if self.target:
            reach.append(self.landing_x(self.target))
        far = min(reach) if sgn > 0 else max(reach)
        return far - sgn * 14 * self.w.u

    # ---- operation ----
    def update(self, dt):
        if not self.present:
            return
        w, u = self.w, self.w.u
        want = self.wanted_sections()
        self.sections += max(-dt * .6, min(dt * .6, want - self.sections))  # climbs / lowers itself
        jib_y = self.mast_top()
        rest = 20 * u
        speed = 70 * u * dt
        self.t += dt

        def move(attr, goal):
            cur = getattr(self, attr)
            if abs(goal - cur) <= speed:
                setattr(self, attr, goal)
                return True
            setattr(self, attr, cur + speed * (1 if goal > cur else -1))
            return False

        working = w.phase == "build" and not self.leaving and not ((w.night or w.storm()) and w.night_shift())
        if self.state == "idle":
            move("hook", rest)
            lv = self.landing_level()
            stocked = sum(self.available(k) for k in self.landings)
            if working and lv and stocked < 12 and w.pile_left[self.side] > self.LOAD:
                self.target, self.state = lv, "to_pile"
        elif self.state == "to_pile":
            if move("hook", rest) and move("trolley", w.piles[self.side]):
                self.state = "lower"
        elif self.state == "lower":
            if move("hook", w.ground - 8 * u - jib_y):
                self.state, self.t = "hitch", 0.0
        elif self.state == "hitch":
            if self.t > 1.0:
                k = min(self.LOAD, w.pile_left[self.side])
                w.pile_left[self.side] -= k
                self.load, self.state = k, "lift"
        elif self.state == "lift":
            top = w.level_y(self.target) - 30 * u - jib_y
            if move("hook", max(rest, top)):
                self.state = "swing"
        elif self.state == "swing":
            if move("trolley", self.landing_x(self.target)):
                self.state = "set_down"
        elif self.state == "set_down":
            if move("hook", w.level_y(self.target) - 6 * u - jib_y):
                self.state, self.t = "unhitch", 0.0
        elif self.state == "unhitch":
            if self.t > .8:
                self.landings[self.target] = self.landings.get(self.target, 0) + self.load
                self.load, self.state = 0, "idle"

    def hit(self, affect):
        """Does a disaster touch the crane anywhere?"""
        if not self.present:
            return False
        w = self.w
        for i in range(int(self.sections) + 1):
            if affect(self.x, w.ground - (i + .5) * w.lift):
                return True
        y = self.mast_top()
        x0, x1 = self.x, self.jib_end()
        return any(affect(x0 + (x1 - x0) * k / 6, y) for k in range(7))

    def collapse(self, in_beam=None):
        """The crane comes apart. in_beam(x, y): a tractor beam is taking it, so the
        pieces inside it are carried up and the rest simply drop."""
        w, u = self.w, self.w.u
        if not self.present:
            return

        def piece(x, y, vx, vy):
            if in_beam and in_beam(x, y):
                w.add_particle(x, y, 0, 0, "pole", abduct=True)
            elif in_beam:
                w.add_particle(x, y, w.rng.uniform(-15, 15) * u, 0, "pole")
            else:
                w.add_particle(x, y, vx, vy, "pole")
        for i in range(int(self.sections) + 1):
            for _ in range(2):
                piece(self.x, w.ground - (i + .5) * w.lift, w.rng.uniform(-90, 90) * u, -w.rng.uniform(20, 120) * u)
        y, x0, x1 = self.mast_top(), self.x, self.jib_end()
        for k in range(8):
            piece(x0 + (x1 - x0) * k / 7, y, w.rng.uniform(-80, 80) * u, -w.rng.uniform(0, 80) * u)
        for lv, n in self.landings.items():
            for _ in range(min(n, 6)):
                w.add_particle(self.landing_x(lv), w.level_y(lv) - 4 * u, w.rng.uniform(-60, 60) * u, -40 * u, "brick")
        self.landings, self.reserved, self.load = {}, {}, 0
        self.present, self.gone = False, True

    def draw(self, cr):
        w, u = self.w, self.w.u
        for lv, n in self.landings.items():  # landing pallets on the walkway
            if n <= 0:
                continue
            x, y = self.landing_x(lv), w.level_y(lv)
            cr.rectangle(x - 10 * u, y - 1.5 * u, 20 * u, 1.5 * u)
            for i in range(min(n, 8)):
                row, col = divmod(i, 4)
                cr.rectangle(x - 9.5 * u + col * 4.8 * u, y - 1.5 * u - (row + 1) * 3.8 * u, 4.3 * u, 3.4 * u)
            cr.fill()
        if not self.present:
            return
        g, x = w.ground, self.x
        top = self.mast_top()
        sgn = -1 if self.side == 0 else 1
        cr.rectangle(x - 7 * u, g - 4 * u, 14 * u, 4 * u)  # foundation
        cr.fill()
        draw_lattice(cr, x, g - 4 * u, x, top, 6 * u)        # mast
        end = self.jib_end()
        draw_lattice(cr, x, top - 3 * u, end, top - 3 * u, 4.5 * u)      # jib
        draw_lattice(cr, x, top - 3 * u, x + sgn * 34 * u, top - 3 * u, 4.5 * u)  # counter-jib
        cr.rectangle(min(x + sgn * 26 * u, x + sgn * 36 * u), top - 2 * u, 10 * u, 8 * u)  # counterweight
        cr.rectangle(x - 4 * u, top - 14 * u, 8 * u, 9 * u)  # cab and tower top
        cr.fill()
        cr.set_line_width(.7 * u)
        for tip in (end, x + sgn * 34 * u):                  # pendant lines
            cr.move_to(x, top - 14 * u)
            cr.line_to(tip, top - 5 * u)
        hook_y = top + self.hook
        cr.move_to(self.trolley, top)
        cr.line_to(self.trolley, hook_y)
        cr.stroke()
        cr.rectangle(self.trolley - 3 * u, top - 1 * u, 6 * u, 3 * u)
        cr.rectangle(self.trolley - 1.5 * u, hook_y, 3 * u, 3 * u)
        cr.fill()
        if self.load:
            cr.rectangle(self.trolley - 9 * u, hook_y + 3 * u, 18 * u, 1.2 * u)
            for i in range(min(self.load, 8)):
                row, col = divmod(i, 4)
                cr.rectangle(self.trolley - 9 * u + col * 4.6 * u, hook_y + 4.2 * u + row * 3.8 * u, 4.2 * u, 3.4 * u)
            cr.fill()
