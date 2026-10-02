"""One monitor's scene: the build cycle, the crew, scaffolding, debris and drawing.

The cycle runs on the wall clock. Its start time is saved, so a week-long build
picks up where it was after a reboot. The monument rises during the first 90%
of the cycle (the crew delivers blocks on schedule); at the end a disaster
hits, the survivors regroup, and the next cycle starts.
"""

import itertools
import math
import random
import time

import cairo

from .config import load_state, save_state
from .disasters import ABDUCT, DISASTERS
from .monuments import BEACONS, MONUMENTS, Monument
from .people import CARRY_WALK, CLIMB, SEAT_H, WALK, Worker, draw_person
from .site import Crane, Scaffold, Truck
from . import astro
from .sky import FIXED_HOURS, Landscape, mix, palette

BUILD_SHARE = 0.9      # of the cycle spent building; the rest it stands finished...
SHORT_BUILD_SHARE = 0.8  # ...except in short cycles, which need longer to take the scaffold down
MAX_CARRY = 3
MAX_CREW = 40          # short cycles hire up to this many workers...
MAX_TIMELAPSE = 6.0    # ...then speed the crew up like a time-lapse...
BLOCK_SCALES = (1.0, 1.5, 2.0, 3.0, 4.0)  # ...then use bigger blocks
NIGHT_SHIFT_MIN_CYCLE = 7200  # cycles at least this long stop work at night
CRANE_MIN_LEVELS = 19         # monuments at least this tall (~300 px) get a tower crane


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "kind", "life", "bounced", "abduct", "dead")

    def __init__(self, x, y, vx, vy, kind, life=0.0, abduct=False):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.kind, self.life, self.abduct = kind, life, abduct
        self.bounced = self.dead = False


class World:
    def __init__(self, W, H, config, key="window", seed=None, cycle=None, persist=True,
                 first_monument=None, clock=time.time, weather=None):
        self.W, self.H = W, H
        self.u = u = H / 720
        self.ground = H - int(58 * u)
        self.gravity = 450 * u
        self.lift = 16 * u
        self.config = config
        self.key = key
        self.cycle_override = cycle
        self.persist = persist
        self.clock = clock
        seed = seed if seed is not None else hash(key) & 0xffff
        self.rng = random.Random(seed ^ int(time.time()))
        self.landscape = Landscape(W, H, self.ground, seed)
        self.sil = palette(20)["sil"]
        self.lights = 0.0
        order_rng = random.Random(seed)
        self.order = list(MONUMENTS)
        order_rng.shuffle(self.order)
        self.first_monument = first_monument

        self.fg = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        self.cr = cairo.Context(self.fg)
        self.rubble = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
        self.hm = [0] * (W + 2)
        self.rubble_dirty = True
        self.particles = []
        self.birds = []
        self.disaster = None
        self.trigger = False
        self.recent = []
        self.collapse_t = 0.0
        self.staff_t = 0.0
        self.night = False
        self.fire_level = 0.0
        self.weather_src = weather   # shared engine.weather.Weather, or None
        self.wx = {"kind": "clear", "amount": 0.0, "cloud": 0.0, "wind": 0.0}
        self.drops = {"rain": [], "snow": []}  # [x, y, speed, drift phase]
        self.wxe = {"cloud": 0.0, "wind": 0.0, "rain": 0.0, "snow": 0.0, "fog": 0.0}  # eased
        self.wx_started = False
        self.sun_screen = None       # where the sun is drawn in the backdrop, set with the sky
        self.pal = palette(12)
        self.loc = astro.location()
        self.clouds = []  # [x, y, speed factor, (width, bumps), shade]; more show as cover grows
        for i in range(16):
            cw = self.rng.uniform(50, 140) * u
            n = self.rng.randint(3, 5)
            bumps = [(-cw / 2 + cw * (k + .5) / n + self.rng.uniform(-4, 4) * u,
                      self.rng.uniform(8, 17) * u * (1 - abs(k + .5 - n / 2) / n)) for k in range(n)]
            self.clouds.append([self.rng.uniform(0, W), self.rng.uniform(.06, .45) * self.ground,
                                self.rng.uniform(.6, 1.4), (cw, bumps), self.rng.uniform(.75, 1)])
        self.bolt = None             # lightning: (points, time left)
        self.next_bolt = 5.0
        self.snow_cover = 0.0
        self.watched = True       # set by the app from Hyprland: nothing covers this monitor
        self.watched_for = 0.0
        self.t_anim = 0.0
        self.rest_x = W * (.07 if self.rng.random() < .5 else .93)  # the crew's container stays put
        self.fire_x = self.rest_x + (55 if self.rest_x < W / 2 else -55) * self.u  # their campfire
        self.camp_seats, self.rest_seats = self.make_seats()
        self.seats = {}           # worker -> seat x it has claimed
        self.guitarist = None     # whoever is playing tonight
        self.stoker = None        # whoever is putting a log on
        self.fire_boost = 0.0     # flare-up after a new log
        self.make_scenery()
        self.trucks = []
        self.workers = [Worker(self, self.rng.uniform(W * .3, W * .7), self.rng) for _ in range(config.workers)]

        state = load_state(key) if persist else None
        now = clock()
        length = self.cycle_len()
        if state and not cycle:
            start, index = state["start"], state["index"]
            if now >= start + length:  # the cycle ended while we were off: show the finale soon
                start = now - length + 20
        else:
            start = now - self.rng.uniform(.25, .6) * self.build_time()
            index = order_rng.randrange(len(self.order))
        self.begin_cycle(start, index)

    # ------------------------------------------------------------ cycle
    def cycle_len(self):
        return self.cycle_override or self.config.cycle

    def build_time(self):
        length = self.cycle_len()
        return (BUILD_SHARE if length >= 600 else SHORT_BUILD_SHARE) * length

    # ---- day and night ----
    def sky_hour(self, t):
        sky = self.config.sky
        if sky == "loop":
            return 24 * (t / self.config.sky_loop % 1)
        if sky == "clock":
            lt = time.localtime(t)
            return lt.tm_hour + lt.tm_min / 60 + lt.tm_sec / 3600
        return FIXED_HOURS.get(sky, 12.0)

    def is_night(self, t):
        if self.config.sky == "clock" and self.loc:  # civil dusk: sun 6 degrees under the horizon
            return astro.sun(t, *self.loc)[0] < -6
        h = self.sky_hour(t) % 24
        return h >= 20.5 or h < 6.3

    def night_shift(self):
        """Long cycles with a real (or looping) sky stop work after dark."""
        return self.config.sky in ("clock", "loop") and self.cycle_len() >= NIGHT_SHIFT_MIN_CYCLE

    def build_schedule(self):
        """Cumulative working seconds across the build, so nights don't count."""
        n, bt = 2000, self.build_time()
        step = bt / n
        shift = self.night_shift()
        cum = [0.0]
        for i in range(n):
            t = self.cycle_start + (i + .5) * step
            cum.append(cum[-1] + (0.0 if shift and self.is_night(t) else step))
        if cum[-1] <= 0:
            cum = [i * step for i in range(n + 1)]
        self.sched = (self.cycle_start, step, cum)

    def work_done(self, t):
        start, step, cum = self.sched
        k = max(0.0, min(len(cum) - 1.0, (t - start) / step))
        i = min(int(k), len(cum) - 2)
        return cum[i] + (cum[i + 1] - cum[i]) * (k - i)

    def due(self, t):
        frac = self.work_done(t) / self.sched[2][-1]
        return int(len(self.mon.bricks) * max(0.0, min(1.0, frac)))

    def begin_cycle(self, start, index):
        self.cycle_start, self.index = start, index
        self.build_schedule()
        if self.persist and not self.cycle_override:
            save_state(self.key, {"start": start, "index": index})
        enabled = [n for n in self.order if n in self.config.wonders] or self.order
        name = self.first_monument or enabled[index % len(enabled)]
        self.first_monument = None
        for block in BLOCK_SCALES:
            self.mon = Monument(name, self.rng, scale=self.u, block=block)
            self.layout_site()
            self.trip = self.estimate_trip()
            self.crew, self.base_timelapse = self.plan_crew()
            if self.base_timelapse <= MAX_TIMELAPSE:
                break
        self.timelapse = self.base_timelapse
        self.extra, self.hire_t = 0, 0.0  # helpers hired while behind schedule
        m, W = self.mon, self.W
        self.monument_mask = cairo.ImageSurface(cairo.FORMAT_A8, m.w, m.h)
        self.mcr = cairo.Context(self.monument_mask)
        self.mcr.set_antialias(cairo.ANTIALIAS_NONE)
        self.standing = {}
        self.placed = 0
        self.assigned = 0
        self.top_level = 0
        self.layout_scaffold()
        self.scaffold = Scaffold(self)
        self.crane = None
        if self.levels >= CRANE_MIN_LEVELS:
            room = [self.piles[0], self.W - self.piles[1]]
            side = 1 if room[1] >= room[0] else 0
            if room[side] > 70 * self.u:
                self.crane = Crane(self, side)
        self.side_total = [0, 0]
        for b in m.bricks:
            self.side_total[self.side_of(b)] += 1
        self.batch = [max(24, math.ceil(t / 3)) for t in self.side_total]
        self.pile_left = [0, 0]
        self.undelivered = list(self.side_total)
        self.phase = "build"
        self.phase_t = 0.0
        self.disaster = None
        self.hm = [0] * (W + 2)
        self.rubble_dirty = True
        self.catch_up(self.due(self.clock()))  # what was built while we weren't running
        self.assigned = self.taken = self.placed
        if self.placed:
            self.settle_site()
        self.staff()

    def settle_site(self):
        """Bring the site to where it would be by now: scaffold up to the working level
        (or already taken down), pallets stocked, nothing in flight. Used on start-up and
        when a monitor is uncovered after a long time."""
        sc, m = self.scaffold, self.mon
        for side in (0, 1):
            sc.progress[side] = [0.0] * len(sc.progress[side])
            sc.crews[side] = 0
        sc.built, sc.reserved = [0, 0], [0, 0]
        if self.placed < len(m.bricks):
            sc.complete_to(self.top_level + 1)
        else:
            sc.rack = [self.levels, self.levels]
            sc.undelivered = [0, 0]
        used = [0, 0]
        for b in m.bricks:
            used[self.side_of(b)] += b.placed
        for s in (0, 1):
            left = self.side_total[s] - used[s]
            self.pile_left[s] = min(self.batch[s], left)
            self.undelivered[s] = left - self.pile_left[s]
        self.trucks = []
        cr = self.crane
        if cr:
            cr.landings, cr.reserved, cr.load, cr.state, cr.hook = {}, {}, 0, "idle", 20 * self.u
            cr.trolley = self.piles[cr.side]
            done = self.placed >= len(m.bricks)
            cr.present, cr.gone, cr.leaving = not done, done, done
            cr.sections = cr.wanted_sections() if not done else 0.0

    def resume(self, gap):
        """The machine was asleep for `gap` seconds: put up what would have been built.
        Everyone climbs down where they are and picks up from there."""
        if self.phase not in ("build", "admire"):
            return  # a disaster in progress simply carries on
        for b in self.mon.bricks:
            b.taken = b.placed
        self.particles = [p for p in self.particles if p.kind != "smoke"]
        for w in self.workers:
            if not w.hidden and not w.leaving:
                w.reset(w.x)
        self.catch_up(self.due(self.clock()))
        self.assigned = self.taken = self.placed
        self.settle_site()
        self.timelapse = self.base_timelapse
        if self.phase == "build" and self.placed >= len(self.mon.bricks):
            self.phase, self.phase_t = "admire", 0.0

    def layout_site(self):
        m, u, W = self.mon, self.u, self.W
        margin = m.w / 2 + 70 * u
        cx = W / 2 + self.rng.uniform(-.06, .06) * W
        cx = max(margin, min(W - margin, cx)) if W > 2 * margin else W / 2
        self.ox, self.oy = int(cx - m.w / 2), self.ground - m.h
        self.mx0, self.mx1, self.mtop = self.ox, self.ox + m.w, self.oy
        self.center = cx
        base = m.rowext[-1]
        self.site = (self.ox + base[0], self.ox + base[1])
        self.piles = [max(14 * u, self.site[0] - 32 * u), min(W - 14 * u, self.site[1] + 32 * u)]
        self.racks = [max(10 * u, self.piles[0] - 24 * u), min(W - 10 * u, self.piles[1] + 24 * u)]

    def estimate_trip(self):
        """Typical seconds for one delivery: pallet, up the ladders, place, back down."""
        bricks = self.mon.bricks
        sample = bricks[::max(1, len(bricks) // 200)]
        total = 0.0
        for b in sample:
            bx = self.ox + b.cx
            height = self.ground - (self.oy + b.bottom)
            dx = abs(self.piles[0 if bx < self.center else 1] - bx)
            total += 2 * height / CLIMB + 1.6 * (dx / CARRY_WALK + dx / WALK)  # plus detours on the deck
        return total / len(sample) + 0.9 + 0.7 * MAX_CARRY

    def plan_crew(self):
        """Crew size and time-lapse factor needed to finish the build on time. The
        factor is fixed for the whole cycle: the crew never visibly speeds up."""
        bricks = self.mon.bricks
        working = self.sched[2][-1]
        rate = len(bricks) / working  # per working second
        # workers busy full time, plus slack for waiting on floors, ladders and trucks
        need = rate * self.trip / MAX_CARRY * 2.0
        crew = max(self.config.workers, min(MAX_CREW, math.ceil(need)))
        # the levels go up one after another (finish the floor, climb, set): that serial
        # work may spill over the schedule into the time the finished monument stands
        levels = max(1, math.ceil((self.ground - self.mtop) / self.lift))
        serial = sum(2 * lv * self.lift / CLIMB + 4 for lv in range(1, levels + 1))
        slack = max(1.0, self.cycle_len() - self.build_time())
        slow = min(MAX_TIMELAPSE * 4, serial * 1.2 / slack)
        return crew, max(1.0, need / crew, slow)

    def staff(self):
        """Hire workers walking in from the edges, or send extra idle ones home."""
        active = [w for w in self.workers if not w.leaving]
        for _ in range(self.crew + self.extra - len(active)):
            self.spawn_worker()
        extra = len(active) - self.crew - self.extra
        for w in active:
            if extra <= 0:
                break
            if not w.busy and not w.hidden:
                w.assign(w.job_leave())
                extra -= 1

    def recover_time(self):
        return min(40.0, max(10.0, .25 * self.cycle_len()))

    def layout_scaffold(self):
        m = self.mon
        self.levels = max(1, math.ceil((self.ground - self.mtop) / self.lift))
        self.ladders = [[0.0] * (self.levels + 2) for _ in range(2)]
        last = (self.site[0] - self.ox, self.site[1] - self.ox)
        for lv in range(1, self.levels + 2):
            y0 = int(self.level_y(lv) - self.oy)
            y1 = int(self.level_y(lv - 1) - self.oy)
            exts = [m.rowext[r] for r in range(max(0, y0), min(m.h, y1)) if m.rowext[r]]
            if exts:
                last = (min(e[0] for e in exts), max(e[1] for e in exts))
            self.ladders[0][lv] = max(6 * self.u, self.ox + last[0] - 7 * self.u)
            self.ladders[1][lv] = min(self.W - 6 * self.u, self.ox + last[1] + 7 * self.u)
        # openings that a deck at each level has to bridge: arches and colonnades in the
        # design, plus anything that hangs (it goes in later, so it's no floor yet)
        floor = [list(row) for row in m.mask]
        for b in m.bricks:
            if b.hanging:
                for x, y, n in b.runs:
                    floor[y][x:x + n] = [False] * n
        self.deck_gaps = [[] for _ in range(self.levels + 2)]
        for lv in range(1, self.levels + 1):
            r = int(self.level_y(lv) - self.oy)
            if 0 <= r < m.h and m.rowext[r]:
                row, (a, b) = floor[r], m.rowext[r]
                x = a
                while x <= b:
                    if not row[x]:
                        g0 = x
                        while x <= b and not row[x]:
                            x += 1
                        if x - g0 > 8 * self.u:  # narrower gaps are simply stepped over
                            self.deck_gaps[lv].append((self.ox + g0 - 1, self.ox + x + 1))
                    x += 1
        # unplaced, stackable blocks per level: a level is walkable once everything below is in
        self.open_blocks = [0] * (self.levels + 2)
        for b in m.bricks:
            if not b.hanging:
                self.open_blocks[self.brick_level(b)] += 1
        self.lowest_open = 0
        self.advance_floor()

    def advance_floor(self):
        while self.lowest_open <= self.levels and self.open_blocks[self.lowest_open] == 0:
            self.lowest_open += 1

    def floor_done(self, lv):
        """Everything below level lv is built, so its floor can carry people and ladders."""
        return self.lowest_open >= lv

    def supported(self, b, extra=()):
        """A block can go in only touching the ground or blocks already in place."""
        if b.gy == 0:
            return True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                k = (b.gx + dx, b.gy + dy)
                if k in self.standing or k in extra:
                    return True
        return False

    def walkway(self, side, lv):
        """x-span of the plank at level lv on one side: from past both ladders to the wall."""
        lad = self.ladders[side][lv]
        nxt = self.ladders[side][min(lv + 1, self.levels)]
        ext = self.row_ext(self.level_y(lv))
        if side == 0:
            far = min(lad, nxt) - 4 * self.u
            edge = self.ox + ext[0] if ext else max(lad, nxt)
        else:
            far = max(lad, nxt) + 4 * self.u
            edge = self.ox + ext[1] if ext else min(lad, nxt)
        return min(far, edge), max(far, edge)

    def stand_x(self, b, side):
        """Where to stand to set block b: beside it, on the floor, a plank or the walkway."""
        lv = self.brick_level(b)
        bx = self.ox + b.cx
        x = bx - 6 * self.u if side == 0 else bx + 6 * self.u
        if lv == 0:
            return x
        ext = self.row_ext(self.level_y(lv))
        lad = self.ladder_x(side, lv)
        if not ext:
            return lad
        lo, hi = (lad, self.ox + ext[1]) if side == 0 else (self.ox + ext[0], lad)
        return max(lo, min(hi, x))

    def level_y(self, lv):
        return self.ground - lv * self.lift

    def ladder_x(self, side, lv):
        return self.ladders[side][min(lv, self.levels + 1)]

    def brick_level(self, b):
        return max(0, min(self.levels, int((self.ground - (self.oy + b.bottom)) // self.lift)))

    def row_ext(self, y):
        r = int(y - self.oy)
        if 0 <= r < self.mon.h:
            return self.mon.rowext[r]
        return None

    def place(self, b):
        if b.placed:
            return
        b.placed = True
        self.placed += 1
        self.standing[(b.gx, b.gy)] = b
        if not b.hanging:
            self.open_blocks[self.brick_level(b)] -= 1
            self.advance_floor()
        for x, y, n in b.runs:
            self.mcr.rectangle(x, y, n, 1)
        self.mcr.fill()
        self.top_level = max(self.top_level, self.brick_level(b))

    def catch_up(self, target):
        """Put up the blocks laid while the wallpaper wasn't running."""
        bricks = self.mon.bricks
        i = 0
        while self.placed < target and i < len(bricks):
            if not bricks[i].placed:
                self.place(bricks[i])
            i += 1

    def side_of(self, b):
        return 0 if self.ox + b.cx < self.center else 1

    def take_from_pile(self, side, k):
        if self.pile_left[side] < k:
            return False
        self.pile_left[side] -= k
        return True

    def add_particle(self, x, y, vx, vy, kind):
        self.particles.append(Particle(x, y, vx, vy, kind))

    def on_config_change(self, old_len):
        if self.phase in ("build", "admire") and not self.cycle_override:
            now = self.clock()
            frac = (now - self.cycle_start) / old_len
            self.cycle_start = now - frac * self.cycle_len()
            if self.persist:
                save_state(self.key, {"start": self.cycle_start, "index": self.index})
        self.build_schedule()
        self.crew, self.base_timelapse = self.plan_crew()
        self.timelapse = self.base_timelapse
        if self.phase in ("build", "admire"):
            self.staff()

    def spawn_worker(self, x=None):
        side = self.rng.choice((-10 * self.u, self.W + 10 * self.u))
        w = Worker(self, side if x is None else x, self.rng)
        w.assign(w.job_return(self.rng.uniform(self.site[0], self.site[1])))
        self.workers.append(w)

    # ------------------------------------------------------------ campsite
    def make_seats(self):
        """Logs round the fire pit and crates by the container, so nobody sits on air."""
        u, fx, rx = self.u, self.fire_x, self.rest_x
        toward = 1 if fx > rx else -1               # from the container to the fire
        box = (rx - 26 * u, rx + 26 * u)            # keep clear of the container itself
        camp = []
        for d in (16, 26, 36, 47, 58):
            for side in (toward, -toward):
                x = fx + side * (d + self.rng.uniform(-2, 2)) * u
                if not box[0] <= x <= box[1] and 4 * u < x < self.W - 4 * u:
                    camp.append(x)
        rest = [rx - toward * (32 + 9 * i) * u for i in range(3)]
        rest = [x for x in rest if 4 * u < x < self.W - 4 * u]
        return camp, rest

    def claim_seat(self, worker, seats):
        mine = self.seats.get(worker)
        if mine in seats:
            return mine
        taken = set(self.seats.values())
        free = [x for x in seats if x not in taken]
        if not free:
            return None
        x = min(free, key=lambda s: abs(s - worker.x) + self.rng.uniform(0, 25) * self.u)
        self.seats[worker] = x
        return x

    def release_seat(self, worker):
        self.seats.pop(worker, None)

    def seat_of(self, worker):
        return self.seats.get(worker)

    def camp_standing_spot(self, worker):
        """No log left: stand in the second row, a little further from the fire."""
        side = self.rng.choice((-1, 1))
        x = self.fire_x + side * self.rng.uniform(20, 66) * self.u
        if abs(x - self.rest_x) < 26 * self.u:
            x = self.fire_x - side * self.rng.uniform(20, 66) * self.u
        return max(4 * self.u, min(self.W - 4 * self.u, x))

    def campfire_on(self):
        return self.night and self.fire_level > .3 and not (self.storm() and self.night_shift())

    def late_night(self):
        if self.config.sky not in ("clock", "loop"):
            return False
        h = self.sky_hour(self.clock()) % 24
        return h >= 23.5 or h < 5

    def stoke(self):
        self.fire_boost = 1.0
        u = self.u
        for _ in range(18):
            self.particles.append(Particle(self.fire_x + self.rng.uniform(-5, 5) * u, self.ground - 6 * u,
                                           self.rng.uniform(-25, 25) * u, -self.rng.uniform(40, 90) * u,
                                           "spark", life=self.rng.uniform(.8, 2)))

    # ------------------------------------------------------------ what is standing
    def _mask(self):
        self.monument_mask.flush()
        return self.monument_mask.get_data(), self.monument_mask.get_stride()

    def solid_span(self, y):
        """Screen x of the outermost standing block pixels in row y, or None."""
        r = int(y - self.oy)
        if not 0 <= r < self.mon.h:
            return None
        data, stride = self._mask()
        row = bytes(data[r * stride:r * stride + self.mon.w])
        i1 = len(row.rstrip(b"\0"))
        if not i1:
            return None
        return self.ox + len(row) - len(row.lstrip(b"\0")), self.ox + i1

    def solid_top(self, x):
        """Screen y of the highest standing block pixel in column x, or None."""
        c = int(x - self.ox)
        if not 0 <= c < self.mon.w:
            return None
        data, stride = self._mask()
        col = bytes(data[c::stride][:self.mon.h])
        n = len(col) - len(col.lstrip(b"\0"))
        return None if n == len(col) else self.oy + n

    def solid_near(self, x, y, r):
        """Is any standing block within r of (x, y)?"""
        data, stride = self._mask()
        m = self.mon
        c0, c1 = max(0, int(x - r - self.ox)), min(m.w - 1, int(x + r - self.ox))
        for row in range(max(0, int(y - r - self.oy)), min(m.h - 1, int(y + r - self.oy)) + 1):
            if c0 <= c1 and any(data[row * stride + c0:row * stride + c1 + 1]):
                return True
        return False

    def trace(self, x0, y0, x1, y1):
        """First point on the segment that hits a standing block, or None."""
        data, stride = self._mask()
        m, u = self.mon, self.u
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / (1.5 * u)))
        for i in range(n + 1):
            k = i / n
            x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
            c, r = int(x - self.ox), int(y - self.oy)
            if 0 <= c < m.w and 0 <= r < m.h and data[r * stride + c]:
                return x, y
        return None

    # ------------------------------------------------------------ disasters
    def begin_disaster(self, name=None):
        if name is None:
            allowed = [n for n in DISASTERS if n in self.config.disasters] or list(DISASTERS)
            options = [n for n in allowed if n not in self.recent] or allowed
            name = self.rng.choice(options)
        self.recent = (self.recent + [name])[-3:]
        d = self.disaster = DISASTERS[name](self)
        self.phase, self.phase_t = "disaster", 0.0
        self.trigger = False
        for t in self.trucks:
            t.leave()
        lucky = self.rng.sample(self.workers, min(len(self.workers), self.rng.randint(3, 5)))
        for w in self.workers:
            w.lucky = w in lucky
            away = 1 if w.x > d.origin_x else -1
            w.assign(w.job_panic(away))
            w.busy = False

    def knock(self, b, vx, vy=0.0, abduct=False):
        key = (b.gx, b.gy)
        if key not in self.standing:
            return
        del self.standing[key]
        self.mcr.set_operator(cairo.OPERATOR_CLEAR)
        for x, y, n in b.runs:
            self.mcr.rectangle(x, y, n, 1)
        self.mcr.fill()
        self.mcr.set_operator(cairo.OPERATOR_OVER)
        self.particles.append(Particle(self.ox + b.cx, self.oy + b.cy, vx, vy, "brick", abduct=abduct))

    def spark(self, x, y, vx, vy, life):
        self.particles.append(Particle(x, y, vx, vy, "spark", life=life))

    def smoke(self, x, y, vx, vy, life):
        self.particles.append(Particle(x, y, vx, vy, "smoke", life=life))

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
            self.knock(alive[k], self.rng.uniform(-20, 20) * self.u, self.rng.uniform(-10, 10) * self.u)

    # ------------------------------------------------------------ update
    def storm(self):
        return self.wx["kind"] == "storm"

    def update_weather(self, dt):
        """Ease towards the reported weather so changes roll in instead of switching."""
        if self.weather_src:
            self.wx = self.weather_src.current()
        wx, u, rng, e = self.wx, self.u, self.rng, self.wxe
        kind = wx["kind"]
        target = {"cloud": wx["cloud"], "wind": wx.get("wind", 0.0),
                  "rain": wx["amount"] if kind in ("rain", "storm") else 0.0,
                  "snow": wx["amount"] if kind == "snow" else 0.0,
                  "fog": wx["amount"] if kind == "fog" else 0.0}
        if not self.wx_started:  # the first report applies at once, later ones roll in
            e.update(target)
            self.wx_started = True
        for key, tau in (("cloud", 25), ("wind", 20), ("rain", 15), ("snow", 20), ("fog", 30)):
            e[key] += (target[key] - e[key]) * min(1.0, dt / tau)
        if self.watched:  # rain and snow are only for looking at
            for key, count, spread in (("rain", 420, 1.0), ("snow", 260, 1.0)):
                pool = self.drops[key]
                want = int(e[key] * count)
                while len(pool) < want:  # new drops start above the screen, so a shower begins gently
                    pool.append([rng.uniform(-40, self.W + 40), rng.uniform(-self.H * spread, -5),
                                 rng.uniform(.8, 1.2), rng.uniform(0, 6)])
                del pool[max(want, 0):]
            for key, fall, push in (("rain", 820, 260), ("snow", 55, 60)):
                for d in self.drops[key]:
                    d[1] += fall * u * d[2] * dt
                    sway = math.sin(self.t_anim * 1.3 + d[3]) * 14 * u if key == "snow" else 0
                    d[0] += (e["wind"] * push * u + sway) * dt
                    if d[1] > self.ground:
                        d[1] -= self.ground + rng.uniform(0, 60) * u
                        d[0] = rng.uniform(-40, self.W + 40)
        drift = (5 + 30 * abs(e["wind"])) * u * (1 if e["wind"] >= 0 else -1)
        span = self.W + 300 * u
        for c in self.clouds:
            c[0] = (c[0] + drift * c[2] * dt + 150 * u) % span - 150 * u
        self.snow_cover = max(0.0, min(1.0, self.snow_cover + (dt / 240 * e["snow"] if e["snow"] > .2 else -dt / 900)))
        if self.bolt:
            pts, left = self.bolt
            self.bolt = (pts, left - dt) if left > dt else None
        if kind == "storm" and e["rain"] > .5:
            self.next_bolt -= dt
            if self.next_bolt <= 0:
                self.next_bolt = rng.uniform(4, 12)
                x = rng.uniform(.1, .9) * self.W
                pts, y = [(x, 0.0)], 0.0
                while y < self.ground:
                    y += rng.uniform(18, 40) * u
                    x += rng.uniform(-22, 22) * u
                    pts.append((x, min(y, self.ground)))
                self.bolt = (pts, .35)

    def update(self, dt):
        self.update_weather(dt)
        self.watched_for = self.watched_for + dt if self.watched else 0.0
        t_now = self.clock()
        self.night = self.is_night(t_now) if self.config.sky in ("clock", "loop") else self.config.sky == "night"
        target = 1.0 if self.night else 0.0
        self.fire_level += max(-dt / 4, min(dt / 3, target - self.fire_level))
        self.fire_boost = max(0.0, self.fire_boost - dt / 6)
        if not self.night and (self.seats or self.guitarist):
            self.seats = {w: x for w, x in self.seats.items() if x in self.rest_seats}
            self.guitarist = self.stoker = None
        if self.watched and self.fire_level > .05 and self.rng.random() < dt * 10 * self.fire_level:
            u = self.u
            self.particles.append(Particle(self.fire_x + self.rng.uniform(-4, 4) * u, self.ground - 8 * u,
                                           self.rng.uniform(-12, 12) * u, -self.rng.uniform(25, 55) * u,
                                           "spark", life=self.rng.uniform(.6, 1.6)))
        self.phase_t += dt
        self.t_anim += dt
        now = self.clock()
        if self.phase in ("build", "admire"):
            # the finale waits until someone is looking: a clear screen for a couple of seconds
            if self.trigger or (now >= self.cycle_start + self.cycle_len() and self.watched_for >= 2.0):
                self.begin_disaster()
            else:
                self.dispatch(now, dt)
                self.staff_t += dt
                if self.staff_t > 3:
                    self.staff_t = 0.0
                    self.staff()
                if self.phase == "build" and self.placed >= len(self.mon.bricks):
                    self.phase, self.phase_t = "admire", 0.0
        elif self.phase == "disaster":
            self.update_disaster(dt)
        elif self.phase == "aftermath":
            if self.crane:
                self.crane.collapse()
            for side in (0, 1):
                if self.scaffold.progress[side][1] > 0:
                    self.scaffold.knock(side, 1)
                for _ in range(min(20, math.ceil(self.pile_left[side] / max(1, self.batch[side]) * 20))):
                    self.add_particle(self.piles[side] + self.rng.uniform(-14, 14) * self.u, self.ground - 8 * self.u,
                                      self.rng.uniform(-50, 50) * self.u, -self.rng.uniform(30, 120) * self.u, "brick")
                for _ in range(min(8, self.scaffold.rack[side])):
                    self.add_particle(self.racks[side], self.ground - 4 * self.u,
                                      self.rng.uniform(-40, 40) * self.u, -self.rng.uniform(20, 80) * self.u, "pole")
                self.pile_left[side] = 0
                self.scaffold.rack[side] = 0
            if self.standing:
                top = sorted(self.standing.values(), key=lambda b: -b.gy)
                for b in top[:max(4, len(top) // 12)]:
                    self.knock(b, self.rng.uniform(-30, 30) * self.u, 0)
            settled = not self.standing and not any(p.kind != "smoke" for p in self.particles)
            if (settled and self.phase_t > 2) or self.phase_t > 14:
                self.disaster = None
                self.phase, self.phase_t = "recover", 0.0
                self.hm0 = list(self.hm)
                for w in self.workers:
                    w.lucky = False
                    w.assign(w.job_return(self.rng.uniform(self.site[0] - 40 * self.u, self.site[1] + 40 * self.u)))
                self.spawn_t = 0.0
        elif self.phase == "recover":
            rt = self.recover_time()
            k = max(0.0, 1 - self.phase_t / (rt * .85))
            self.hm = [int(h * k) for h in self.hm0]
            self.rubble_dirty = True
            self.spawn_t += dt
            if len(self.workers) < self.config.workers and self.spawn_t > rt / (self.config.workers + 2):
                self.spawn_t = 0
                self.spawn_worker()
            if self.phase_t > rt:
                self.begin_cycle(now, self.index + 1)
        wdt = dt * (self.timelapse if self.phase in ("build", "admire") else 1.0)
        for w in list(self.workers):
            w.tick(wdt)
        if any(w.gone for w in self.workers):
            for w in self.workers:
                if w.gone:
                    self.release_seat(w)
            self.workers = [w for w in self.workers if not w.gone]
        if self.crane:
            self.crane.update(wdt)
        for t in self.trucks:
            t.update(wdt if t.state != "out" or self.phase in ("build", "admire") else dt * 1.5)
        self.trucks = [t for t in self.trucks if not t.done]
        self.update_particles(dt)
        self.update_birds(dt)

    def dispatch(self, now, dt):
        bricks = self.mon.bricks
        n = len(bricks)
        # falling behind never makes anyone hurry: an extra hand walks in to help,
        # and goes home again once the work has caught up
        lag = self.due(now) - self.placed
        self.hire_t += dt
        if lag > max(4, n // 50) and self.hire_t > 10 and self.crew + self.extra < MAX_CREW:
            self.extra += 1
            self.hire_t = 0.0
        elif lag <= 0 and self.extra and self.hire_t > 30:
            self.extra -= 1
            self.hire_t = 0.0
        while self.assigned < n and (bricks[self.assigned].taken or bricks[self.assigned].placed):
            self.assigned += 1
        if (self.night or self.storm()) and self.night_shift():
            return  # after dark, or in a thunderstorm, nobody starts anything new
        self.order_trucks()
        sc = self.scaffold
        free = [w for w in self.workers if not w.busy and not w.hidden and not w.leaving and w.level == 0]
        if self.phase == "admire":
            cr = self.crane
            if cr and cr.present:  # the crane lowers itself, then a truck fetches it
                cr.leaving = True
                if cr.ready_to_go() and not any(t.crane == "out" for t in self.trucks):
                    self.trucks.append(Truck(self, cr.side, 0, 0, crane="out"))
            for side in (0, 1):  # take the scaffold down, working from the top to the ground
                if sc.built[side] and not sc.crews[side] and free:
                    levels = list(range(sc.built[side], 0, -1))
                    sc.crews[side] += 1
                    w = free.pop()
                    w.assign(w.job_dismantle(side, levels), busy=True)
            return
        upcoming = list(itertools.islice((b for b in bricks[self.assigned:] if not (b.taken or b.placed)), 80))
        for side in (0, 1):  # keep the scaffold a level ahead of the work
            need = max((self.brick_level(b) for b in upcoming if self.side_of(b) == side), default=0)
            want = min(self.levels, need + 1) if need else 0
            if sc.reserved[side] < want and sc.crews[side] < 2 and sc.rack[side] and free:
                k = min(4, want - sc.reserved[side], sc.rack[side])
                levels = list(range(sc.reserved[side] + 1, sc.reserved[side] + k + 1))
                sc.reserved[side] += k
                sc.rack[side] -= k
                sc.crews[side] += 1
                w = min(free, key=lambda o: abs(o.x - self.racks[side]))
                free.remove(w)
                w.assign(w.job_scaffold(side, levels), busy=True)
        ahead = self.due(now + self.trip / self.timelapse)
        anyone = [w for w in self.workers if not w.busy and not w.hidden and not w.leaving]
        free = [w for w in anyone if w.level == 0]
        cr = self.crane if self.crane and self.crane.present else None
        while self.taken < ahead and anyone and self.assigned < n:
            window = list(itertools.islice((b for b in bricks[self.assigned:] if not (b.taken or b.placed)), 160))

            def ready(b, extra=()):
                side = self.side_of(b)
                lv = self.brick_level(b)
                return ((b.hanging or self.floor_done(lv)) and lv <= sc.reserved[side]
                        and self.supported(b, extra))
            first = next((b for b in window if ready(b)), None)
            if first is None:
                break  # nothing can go in yet without floating: wait for the floor / scaffold
            side = self.side_of(first)
            job, keys = [first], {(first.gx, first.gy)}
            near = sorted((b for b in window if b is not first and self.side_of(b) == side),
                          key=lambda b: abs(b.cx - first.cx) + abs(b.gy - first.gy) * 4)
            for b in near:
                if len(job) >= min(MAX_CARRY, ahead - self.taken):
                    break
                if abs(b.cx - first.cx) < 40 * self.u and ready(b, keys):
                    job.append(b)
                    keys.add((b.gx, b.gy))
            for b in job:
                b.taken = True
            self.taken += len(job)
            while self.assigned < n and (bricks[self.assigned].taken or bricks[self.assigned].placed):
                self.assigned += 1
            blv = self.brick_level(first)
            landing = cr.stocked_landing(len(job), blv) if cr and blv >= 3 else None
            if landing:
                cr.reserve(landing, len(job))  # fetched from the crane's landing up on the walkway
                lx = cr.landing_x(landing)
                w = min(anyone, key=lambda o: abs(o.level - landing) * 40 + abs(o.x - lx))
            else:
                landing = None
                w = min(anyone, key=lambda o: o.level * 40 + abs(o.x - self.piles[side]))
            anyone.remove(w)
            if w in free:
                free.remove(w)
            w.assign(w.job_deliver(job, side, landing), busy=True)

    def order_trucks(self):
        cr = self.crane
        if cr and not cr.present and not cr.gone and not any(t.crane == "in" for t in self.trucks):
            self.trucks.append(Truck(self, cr.side, 0, 0, crane="in"))
        sc = self.scaffold
        for side in (0, 1):
            if any(t.side == side and not t.done for t in self.trucks):
                continue
            low = self.pile_left[side] < max(6, self.batch[side] * .3)
            # the crane serves both sides from its pallet, so a pallet can run short
            # of its own side's share: then the truck brings blocks from the other's
            source = side if self.undelivered[side] else 1 - side
            if (low and self.undelivered[source]) or (sc.undelivered[side] and sc.rack[side] < 2):
                blocks = min(self.undelivered[source], self.batch[side])
                self.undelivered[source] -= blocks
                self.trucks.append(Truck(self, side, blocks, sc.undelivered[side]))

    def update_disaster(self, dt):
        d = self.disaster
        d.update(dt)
        for b in list(self.standing.values()):
            r = d.affect(self.ox + b.cx, self.oy + b.cy)
            if r == ABDUCT:
                self.knock(b, 0, 0, abduct=True)
            elif r:
                self.knock(b, *r)
        for w in list(self.workers):
            if w.hidden or w.lucky:
                continue
            r = d.affect(w.x, w.y - 9 * self.u)
            if r:
                self.workers.remove(w)
                vx, vy = (0, 0) if r == ABDUCT else r
                self.particles.append(Particle(w.x, w.y - 9 * self.u, vx, vy, "body", abduct=r == ABDUCT))
        if self.crane and self.crane.hit(d.affect):
            self.crane.collapse()
        sc = self.scaffold
        for side, lv in list(sc.sections()):
            if sc.progress[side][lv] > 0 and d.affect(self.ladders[side][lv], self.level_y(lv) + self.lift / 2):
                sc.knock(side, lv)
        self.collapse_t += dt
        if self.collapse_t > .3:
            self.collapse_t = 0
            self.collapse_check()
        if d.done:
            self.phase, self.phase_t = "aftermath", 0.0

    def update_particles(self, dt):
        d, g, hm, u = self.disaster, self.ground, self.hm, self.u
        alive = []
        for p in self.particles:
            if p.kind == "spark":
                p.life -= dt
                p.x += (p.vx + math.sin(p.life * 9) * 8 * u) * dt
                p.y += p.vy * dt
                if p.life > 0:
                    alive.append(p)
                continue
            if p.kind == "smoke":
                p.life -= dt
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.vx *= 1 - dt
                p.vy = p.vy * (1 - dt) - 10 * u * dt
                if p.life > 0:
                    alive.append(p)
                continue
            if p.abduct:
                if d:
                    d.force(p, dt)
                else:
                    p.abduct = False
            else:
                p.vy += self.gravity * dt
                if d:
                    d.force(p, dt)
            p.life += dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.dead or p.x < -20 or p.x > self.W + 20 or p.y > self.H + 20 or p.y < -200 * u:
                continue
            ix = min(self.W - 1, max(1, int(p.x)))
            floor = g - hm[ix]
            if p.y >= floor and p.vy > 0 and not p.abduct:
                if not p.bounced and p.vy > 240 * u:
                    p.bounced = True
                    p.vy *= -.25
                    p.vx *= .5
                    p.y = floor - .1
                else:
                    add = 4 if p.kind == "brick" else 1 if p.kind == "pole" else 2
                    for j in (ix - 1, ix, ix + 1):
                        hm[j] += add
                    self.rubble_dirty = True
                    continue
            alive.append(p)
        self.particles = alive
        if self.rubble_dirty:
            lim = 2
            for _ in range(4):
                for x in range(self.W):
                    diff = hm[x] - hm[x + 1]
                    if diff > lim:
                        hm[x] -= 1
                        hm[x + 1] += 1
                    elif diff < -lim:
                        hm[x] += 1
                        hm[x + 1] -= 1

    def update_birds(self, dt):
        rng, u = self.rng, self.u
        if not self.birds and rng.random() < dt / 40:
            d = rng.choice((-1, 1))
            x0 = -20 * u if d > 0 else self.W + 20 * u
            y0 = rng.uniform(.1, .4) * self.ground
            self.birds = [[x0 - d * i * rng.uniform(14, 24) * u, y0 + rng.uniform(-14, 14) * u, d, rng.uniform(0, 6)]
                          for i in range(rng.randint(2, 6))]
        for b in self.birds:
            b[0] += b[2] * 38 * u * dt
            b[3] += dt * 7
        self.birds = [b for b in self.birds if -80 * u < b[0] < self.W + 80 * u]

    # ------------------------------------------------------------ drawing
    def make_scenery(self):
        W, H, g, u, rng = self.W, self.H, self.ground, self.u, self.rng
        self.scenery = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
        cr = cairo.Context(self.scenery)
        cr.rectangle(0, g, W, H - g)
        cr.fill()
        camp = (min(self.rest_x, self.fire_x) - 40 * u, max(self.rest_x, self.fire_x) + 60 * u)
        for _ in range(rng.randint(5, 9)):
            x = rng.choice((rng.uniform(8, W * .14), rng.uniform(W * .86, W - 8)))
            if camp[0] < x < camp[1]:
                continue  # keep the campsite clear
            kind = rng.random()
            th = rng.uniform(26, 58) * u
            cr.rectangle(x - 1 * u, g - th * .45, 2 * u, th * .45 + 1)
            cr.fill()
            if kind < .4:  # cypress
                cr.save()
                cr.translate(x, g - th * .55)
                cr.scale(th * .13, th * .5)
                cr.arc(0, 0, 1, 0, math.tau)
                cr.restore()
                cr.fill()
            elif kind < .7:  # round tree
                for _ in range(5):
                    r = th * rng.uniform(.18, .28)
                    cr.arc(x + rng.uniform(-.2, .2) * th, g - th * rng.uniform(.55, .8), r, 0, math.tau)
                    cr.fill()
            else:  # pine
                for k in range(3):
                    wd = th * (.32 - k * .08)
                    yb = g - th * (.3 + k * .22)
                    cr.move_to(x - wd, yb)
                    cr.line_to(x + wd, yb)
                    cr.line_to(x, yb - th * .38)
                    cr.close_path()
                    cr.fill()
        # gentle grass texture on the ground line
        for x in range(0, W, 2):
            if rng.random() < .25:
                cr.rectangle(x, g - rng.uniform(.5, 2.2) * u, 1, 3 * u)
        cr.fill()
        self.scenery.flush()

    def draw_rubble(self):
        cr = cairo.Context(self.rubble)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.move_to(0, self.ground + 1)
        for x in range(0, self.W + 1, 2):
            cr.line_to(x, self.ground - self.hm[min(x, self.W)] + 1)
        cr.line_to(self.W, self.ground + 1)
        cr.close_path()
        cr.fill()
        self.rubble.flush()
        self.rubble_dirty = False

    def draw_site(self, cr):
        u = self.u
        for side in (0, 1):
            px = self.piles[side]
            count = min(20, math.ceil(20 * self.pile_left[side] / max(1, self.batch[side])))
            cr.rectangle(px - 15 * u, self.ground - 2 * u, 30 * u, 2 * u)  # the pallet
            for i in range(count):
                row, col = divmod(i, 5)
                cr.rectangle(px - 14 * u + col * 5.6 * u + row * 1.4 * u, self.ground - 2 * u - (row + 1) * 4.4 * u,
                             5 * u, 3.9 * u)
            cr.fill()
        self.scaffold.draw_racks(cr)
        for sx in self.rest_seats:  # crates to sit on during a break
            cr.rectangle(sx - 3, self.ground - SEAT_H, 6, SEAT_H)
        cr.fill()
        # site container where the crew rests
        x, y = self.rest_x, self.ground
        cr.rectangle(x - 22 * u, y - 18 * u, 44 * u, 18 * u)
        cr.rectangle(x - 23 * u, y - 19 * u, 46 * u, 2 * u)
        cr.fill()
        if self.lights > 0:
            cr.set_source_rgba(1, .8, .45, self.lights)
            cr.rectangle(x - 15 * u, y - 13 * u, 9 * u, 6 * u)
            cr.fill()
            cr.set_source_rgb(*self.sil)

    def draw_sky_weather(self, cr):
        """Behind the scene: the overcast veil and drifting clouds."""
        e, u, p = self.wxe, self.u, self.pal
        night = p["stars"]
        if e["cloud"] > .3:
            cr.set_source_rgba(.52, .55, .6, (e["cloud"] - .3) * .55 * (1 - .7 * night))
            cr.paint()
        if e["rain"] > .4:  # heavy rain: a darker, leaden sky
            cr.set_source_rgba(.22, .24, .3, (e["rain"] - .4) * .55 * (1 - .6 * night))
            cr.paint()
        if self.sun_screen and e["cloud"] > .35:  # thick cloud hides the sun and its glow
            sx, sy = self.sun_screen
            k = min(1.0, (e["cloud"] - .35) / .5) * .92
            veil = cairo.RadialGradient(sx, sy, 0, sx, sy, 230 * u)
            veil.add_color_stop_rgba(0, .55, .58, .63, k)
            veil.add_color_stop_rgba(.25, .55, .58, .63, k * .8)
            veil.add_color_stop_rgba(1, .55, .58, .63, 0)
            cr.set_source(veil)
            cr.arc(sx, sy, 230 * u, 0, math.tau)
            cr.fill()
        shown = 2 + e["cloud"] * (len(self.clouds) - 2)
        day_col = mix(p["horizon"], (1, 1, 1), .55)
        col = mix(mix(day_col, mix(p["top"], p["far"], .6), night), (.42, .44, .5), e["cloud"] * .7)
        for i, (x, y, _, (cw, bumps), shade) in enumerate(self.clouds):
            a = max(0.0, min(1.0, shown - i))
            if a <= 0:
                break
            cr.set_source_rgba(*col, a * shade * (.55 - .2 * night) * (1 + e["cloud"]))
            h = 7 * u
            cr.save()
            cr.rectangle(x - cw, y - 60 * u, 2 * cw, 60 * u)
            cr.clip()
            cr.new_path()
            cr.rectangle(x - cw / 2 + h, y - 2 * h, cw - 2 * h, 2 * h)
            for ex in (x - cw / 2 + h, x + cw / 2 - h):
                cr.new_sub_path()
                cr.arc(ex, y - h, h, 0, math.tau)
            for dx, r in bumps:
                cr.new_sub_path()
                cr.arc(x + dx, y - h - r * .3, r, 0, math.tau)
            cr.fill()
            cr.restore()

    def draw_weather(self, cr):
        e, u = self.wxe, self.u
        if e["fog"] > .02:
            fog = cairo.LinearGradient(0, self.ground - 320 * u, 0, self.ground)
            fog.add_color_stop_rgba(0, .8, .82, .86, 0)
            fog.add_color_stop_rgba(1, .8, .82, .86, .55 * e["fog"])
            cr.set_source(fog)
            cr.rectangle(0, self.ground - 320 * u, self.W, 320 * u)
            cr.fill()
        if self.drops["snow"]:
            cr.set_source_rgba(.95, .96, 1, .85)
            for x, y, k, _ in self.drops["snow"]:
                cr.arc(x, y, 1.1 * u * k, 0, math.tau)
                cr.fill()
        if self.drops["rain"]:
            slant = e["wind"] * 260 / 820
            cr.set_source_rgba(.78, .82, .9, .35)
            cr.set_line_width(.9 * u)
            for x, y, k, _ in self.drops["rain"]:
                cr.move_to(x, y)
                cr.line_to(x - slant * 11 * u * k, y - 11 * u * k)
            cr.stroke()
        if self.bolt:
            pts, left = self.bolt
            flicker = 1.0 if left > .25 or .1 < left < .17 else .35
            cr.set_source_rgba(.85, .9, 1, .18 * flicker)
            cr.paint()
            for wd, a in ((5, .35), (1.6, 1)):
                cr.set_source_rgba(.95, .97, 1, a * flicker)
                cr.set_line_width(wd * u)
                cr.move_to(*pts[0])
                for pt in pts[1:]:
                    cr.line_to(*pt)
                cr.stroke()

    def draw_campfire(self, cr):
        u, g = self.u, self.ground
        for sx in self.camp_seats:  # logs round the fire pit
            cr.rectangle(sx - 4.5, g - SEAT_H, 9, SEAT_H)
        cr.fill()
        k = self.fire_level * (1 + .45 * self.fire_boost)
        if k <= .01:
            return
        x, t = self.fire_x, self.t_anim
        glow = cairo.RadialGradient(x, g - 8 * u, 0, x, g - 8 * u, 85 * u * k)
        glow.add_color_stop_rgba(0, 1, .62, .25, .5 * k)
        glow.add_color_stop_rgba(1, 1, .45, .15, 0)
        cr.set_source(glow)
        cr.arc(x, g - 8 * u, 85 * u * k, 0, math.tau)
        cr.fill()
        cr.set_source_rgb(*self.sil)  # crossed logs
        cr.set_line_width(2.4 * u)
        for a, b in ((-1, 1), (1, -1)):
            cr.move_to(x + a * 8 * u, g)
            cr.line_to(x + b * 7 * u, g - 4 * u)
        cr.stroke()
        for col, scale in (((1, .45, .12), 1.0), ((1, .78, .3), .62), ((1, .96, .75), .3)):
            cr.set_source_rgba(*col, .92)
            for i in range(5):
                fx = x + (i - 2) * 3 * u * scale
                h = (11 + 6 * math.sin(t * 9 + i * 1.7) + 4 * math.sin(t * 13.7 + i)) * u * k * scale
                lean = math.sin(t * 5 + i) * 2 * u
                cr.move_to(fx - 3 * u * scale, g - 3 * u)
                cr.curve_to(fx - 3 * u * scale, g - h * .5, fx + lean, g - h * .8, fx + lean, g - 3 * u - h)
                cr.curve_to(fx + lean, g - h * .8, fx + 3 * u * scale, g - h * .5, fx + 3 * u * scale, g - 3 * u)
                cr.close_path()
                cr.fill()
        cr.set_source_rgb(*self.sil)

    def draw_beacon(self, cr):
        spot = BEACONS.get(self.mon.name)
        if not spot or len(self.standing) < .97 * len(self.mon.bricks):
            return
        u = self.u
        x, y = self.ox + spot[0] * u, self.ground - spot[1] * u
        flicker = .85 + .15 * math.sin(self.t_anim * 9) * math.sin(self.t_anim * 5.3)
        strength = (1.0 if self.lights else .45) * flicker
        r = (60 if self.lights else 24) * u
        glow = cairo.RadialGradient(x, y, 0, x, y, r)
        glow.add_color_stop_rgba(0, 1, .93, .7, strength)
        glow.add_color_stop_rgba(.15, 1, .7, .3, .7 * strength)
        glow.add_color_stop_rgba(1, 1, .5, .2, 0)
        cr.set_source(glow)
        cr.arc(x, y, r, 0, math.tau)
        cr.fill()
        cr.set_source_rgb(*self.sil)

    def render(self):
        cr, u = self.cr, self.u
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        self.draw_sky_weather(cr)
        cr.set_source_rgb(*self.sil)
        cr.set_line_width(1.3 * u)
        for x, y, d, ph in self.birds:
            flap = math.sin(ph) * 3 * u
            cr.move_to(x - 5 * u, y - flap)
            cr.line_to(x, y)
            cr.line_to(x + 5 * u, y - flap)
        cr.stroke()
        d = self.disaster
        cr.save()
        if d and d.shake:
            cr.translate(self.rng.uniform(-d.shake, d.shake), self.rng.uniform(-d.shake, d.shake) / 2)
        if d:
            d.draw_back(cr)
        cr.set_source_rgb(*self.sil)
        cr.mask_surface(self.monument_mask, self.ox, self.oy)
        self.scaffold.draw(cr)
        if self.crane:
            self.crane.draw(cr)
        self.draw_site(cr)
        for t in self.trucks:
            t.draw(cr)
        self.draw_campfire(cr)
        if self.rubble_dirty:
            self.draw_rubble()
        cr.mask_surface(self.rubble, 0, 0)
        for w in self.workers:
            if not w.hidden:
                draw_person(cr, w.x, w.y, w.f, w.pose, w.ph, carry=w.carry, poles=w.poles)
                if w.held:
                    hx, hy = w.held
                    bw, bh = self.mon.bw * u, self.mon.bh * u
                    cr.rectangle(hx - bw / 2, hy - bh / 2, bw, bh)
                    cr.fill()
        for p in self.particles:
            if p.kind == "brick":
                cr.rectangle(p.x - 2.5 * u, p.y - 2 * u, 5 * u, 4 * u)
                cr.fill()
            elif p.kind == "pole":
                a = p.life * 6
                cr.set_line_width(1.3 * u)
                cr.move_to(p.x - math.cos(a) * 9 * u, p.y - math.sin(a) * 9 * u)
                cr.line_to(p.x + math.cos(a) * 9 * u, p.y + math.sin(a) * 9 * u)
                cr.stroke()
            elif p.kind == "body":
                draw_person(cr, p.x, p.y + 9 * u, 1, "tumble", p.life * 6, rot=p.life * 7)
        for p in self.particles:
            if p.kind == "spark":
                cr.set_source_rgba(1, .75, .35, min(1.0, p.life))
                cr.arc(p.x, p.y, .9 * u, 0, math.tau)
                cr.fill()
        for p in self.particles:
            if p.kind == "smoke":
                r = (6 + (4 - p.life) * 5) * u
                cr.set_source_rgba(*self.sil, .25 * min(1.0, p.life / 2))
                cr.arc(p.x, p.y, r, 0, math.tau)
                cr.fill()
        cr.set_source_rgb(*self.sil)
        cr.mask_surface(self.scenery, 0, 0)
        if self.snow_cover > .02:  # snow settling on the ground
            cr.set_source_rgba(.92, .94, .98, .85)
            cr.rectangle(0, self.ground, self.W, 3 * u * self.snow_cover)
            cr.fill()
        self.draw_beacon(cr)
        if d:
            d.draw_front(cr)
        cr.restore()
        self.draw_weather(cr)
        if d and d.flash > 0:
            cr.set_source_rgba(1, .97, .85, d.flash * .75)
            cr.paint()
        self.fg.flush()
        return self.fg

    def set_palette(self, pal, hour):
        self.pal = pal
        self.sil = pal["sil"]
        h = hour % 24
        self.lights = 0.9 if (h >= 19.5 or h < 6.5) else 0.0
