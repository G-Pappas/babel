#!/usr/bin/env python3
"""Babel - a live wallpaper for Omarchy.

A small crew builds a world monument block by block; at the end of each cycle a
disaster flattens it and the survivors start the next one. The cycle length is
set in ~/.config/babel-live/config.toml (minutes to weeks).

  babel-live.py                  live on every monitor (layer behind windows)
  babel-live.py --window         in a normal window, for development
  babel-live.py --snapshot OUT   render one frame to a PNG and exit
  babel-live.py --disaster-now   make the running wallpaper's disaster happen now
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cairo  # noqa: E402

from engine.config import Config, parse_duration  # noqa: E402
from engine.hypr import Hyprland  # noqa: E402
from engine.weather import Weather  # noqa: E402
from engine.disasters import DISASTERS  # noqa: E402
from engine.monuments import MONUMENTS  # noqa: E402
from engine.sky import sky_state  # noqa: E402
from engine.world import World  # noqa: E402

FPS = 15
ART_H = 720
SKY_REFRESH = 30.0
LIVE_STATUS = Path.home() / ".local/state/babel-live/live.json"
SCRIPT = str(Path(__file__).resolve())


def art_size(dev_w, dev_h):
    px = max(1, round(dev_h / ART_H))
    return -(-dev_w // px), -(-dev_h // px)


def picture(config):
    return None if config.background == "live" else os.path.expanduser(config.background)


def running_pids():
    pids = []
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit() and int(proc.name) != os.getpid():
            try:
                argv = (proc / "cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            if len(argv) >= 2 and argv[1].decode(errors="replace") == SCRIPT and b"--window" not in argv:
                pids.append(int(proc.name))
    return pids


def snapshot(args):
    config = Config()
    W, H = art_size(3840, 2160)
    clock = [time.time()]
    cycle = parse_duration(args.cycle) if args.cycle else 3600.0
    if args.weather:
        config.weather = args.weather
    world = World(W, H, config, seed=args.seed, cycle=cycle, persist=False,
                  first_monument=args.monument, clock=lambda: clock[0], weather=Weather(config))
    world.first_monument = args.monument
    world.begin_cycle(clock[0] - args.progress * world.build_time(), world.index)
    if args.disaster:
        world.catch_up(len(world.mon.bricks))
        world.begin_disaster(args.disaster)
    step = 1 / FPS
    for _ in range(int(args.at * FPS)):
        clock[0] += step
        world.update(step)
    state = sky_state(time.time(), config, world.landscape, world.loc, args.hour)
    bg, pal = world.landscape.render(W * args.scale, H * args.scale, state, time.time(), picture(config))
    world.set_palette(pal, state["hour"])
    world.sun_screen = state["sun"]
    fg = world.render()
    cr = cairo.Context(bg)
    cr.scale(args.scale, args.scale)
    cr.set_source_surface(fg, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)
    cr.paint()
    bg.write_to_png(args.snapshot)
    print(f"{args.snapshot}: phase={world.phase} monument={world.mon.name} "
          f"placed={world.placed}/{len(world.mon.bricks)} workers={len(world.workers)}")


def run_gtk(args):
    lib = "/usr/lib/libgtk4-layer-shell.so"
    if not args.window and lib not in os.environ.get("LD_PRELOAD", ""):
        env = dict(os.environ, LD_PRELOAD=(lib + " " + os.environ.get("LD_PRELOAD", "")).strip())
        os.execve(sys.executable, [sys.executable, SCRIPT] + sys.argv[1:], env)

    # Uploading a fresh frame texture is ~3x cheaper on the GL renderer than on Vulkan.
    os.environ.setdefault("GSK_RENDERER", "ngl")
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

    config = Config()
    cycle = parse_duration(args.cycle) if args.cycle else None
    weather = Weather(config)

    def texture(surface):
        data = GLib.Bytes.new(bytes(surface.get_data()))
        fmt = Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED if surface.get_format() == cairo.FORMAT_ARGB32 \
            else Gdk.MemoryFormat.B8G8R8X8
        return Gdk.MemoryTexture.new(surface.get_width(), surface.get_height(), fmt, data, surface.get_stride())

    class Scene(Gtk.Widget):
        def __init__(self, world, dev_w, dev_h, connector=None):
            super().__init__()
            self.world = world
            self.connector = connector
            self.visible = True
            self.hidden_at = 0.0
            self.bg_size = (max(1, dev_w // 2), max(1, dev_h // 2))
            self.bg = self.fg = None
            self.sky_t = -1e9

        def frame(self, dt, now):
            refresh = SKY_REFRESH
            if config.sky == "loop":  # keep the sun moving smoothly through a fast day
                refresh = min(SKY_REFRESH, max(1.0, config.sky_loop / 400))
            if now - self.sky_t > refresh:
                self.sky_t = now
                state = sky_state(time.time(), config, self.world.landscape, self.world.loc, args.hour)
                surf, pal = self.world.landscape.render(*self.bg_size, state, time.time(), picture(config))
                self.world.set_palette(pal, state["hour"])
                self.world.sun_screen = state["sun"]
                self.bg = texture(surf)
            self.world.update(dt)
            self.fg = texture(self.world.render())
            self.queue_draw()

        def do_snapshot(self, snap):
            rect = Graphene.Rect().init(0, 0, self.get_width(), self.get_height())
            if self.bg:
                snap.append_scaled_texture(self.bg, Gsk.ScalingFilter.LINEAR, rect)
            if self.fg:
                snap.append_scaled_texture(self.fg, Gsk.ScalingFilter.LINEAR, rect)

    app = Gtk.Application(application_id=None)
    scenes, windows = [], []

    def build():
        for w in windows:
            w.destroy()
        windows.clear()
        scenes.clear()
        if args.window:
            W, H = art_size(1280, 720)
            win = Gtk.Window(application=app, title="Babel")
            win.set_default_size(1280, 720)
            sc = Scene(World(W, H, config, key="window", cycle=cycle or 600.0, persist=False,
                             first_monument=args.monument, weather=weather), 1280, 720)
            win.set_child(sc)
            win.present()
            windows.append(win)
            scenes.append(sc)
            return False
        monitors = Gdk.Display.get_default().get_monitors()
        for i in range(monitors.get_n_items()):
            mon = monitors.get_item(i)
            geo = mon.get_geometry()
            scale = mon.get_scale() if hasattr(mon, "get_scale") else mon.get_scale_factor()
            dev_w, dev_h = round(geo.width * scale), round(geo.height * scale)
            W, H = art_size(dev_w, dev_h)
            key = f"monitor-{mon.get_connector() or i}"
            world = World(W, H, config, key=key, cycle=cycle, persist=cycle is None,
                          first_monument=args.monument if i == 0 else None, weather=weather)
            win = Gtk.Window(application=app)
            Layer.init_for_window(win)
            Layer.set_layer(win, Layer.Layer.BOTTOM)
            Layer.set_namespace(win, "babel-live")
            Layer.set_monitor(win, mon)
            for edge in (Layer.Edge.TOP, Layer.Edge.BOTTOM, Layer.Edge.LEFT, Layer.Edge.RIGHT):
                Layer.set_anchor(win, edge, True)
            Layer.set_exclusive_zone(win, -1)
            Layer.set_keyboard_mode(win, Layer.KeyboardMode.NONE)
            sc = Scene(world, dev_w, dev_h, mon.get_connector())
            win.set_child(sc)
            win.present()
            win.get_surface().set_input_region(cairo.Region())
            windows.append(win)
            scenes.append(sc)
        return False

    last = [time.monotonic()]

    status_t = [0.0]

    def write_status(now):
        """What each monitor is doing, for the bar widget's header."""
        if now - status_t[0] < 2:
            return
        status_t[0] = now
        rows = []
        for sc in scenes:
            w = sc.world
            rows.append({"monitor": w.key, "monument": w.mon.name, "phase": w.phase,
                         "placed": w.placed, "total": len(w.mon.bricks), "workers": len(w.workers)})
        try:
            LIVE_STATUS.parent.mkdir(parents=True, exist_ok=True)
            tmp = LIVE_STATUS.with_suffix(".tmp")
            tmp.write_text(json.dumps({"time": time.time(), "monitors": rows}))
            tmp.replace(LIVE_STATUS)
        except OSError:
            pass

    hypr = Hyprland() if not args.window else None

    def refresh_visibility():
        """Covered monitors stop drawing; uncovered ones catch up before they're seen."""
        clear = hypr.clear_monitors() if hypr else {}
        now = time.monotonic()
        for sc in scenes:
            visible = clear.get(sc.connector, True)
            if visible and not sc.visible:
                sc.world.resume(now - sc.hidden_at)
                sc.sky_t = -1e9
            elif not visible and sc.visible:
                sc.hidden_at = now
            sc.visible = visible
            sc.world.watched = visible
        return True

    pending = [False]

    def on_hypr_event(*_):
        hypr.drain()
        if not pending[0]:  # a burst of events (workspace switch) is handled once
            pending[0] = True
            GLib.timeout_add(60, lambda: (pending.__setitem__(0, False), refresh_visibility()) and False)
        return True

    def tick():
        now = time.monotonic()
        dt = min(0.25, now - last[0])
        last[0] = now
        for sc in scenes:
            if sc.visible:  # nobody can see a covered monitor: don't draw it at all
                sc.frame(dt, now)
        if not args.window:
            write_status(now)
        return True

    def check_config():
        old = config.cycle
        if config.reload():
            for sc in scenes:
                sc.world.on_config_change(old)
                sc.sky_t = -1e9
        return True

    def disaster_now():
        for sc in scenes:
            sc.world.trigger = True
        return True

    def activate(app):
        app.hold()
        build()
        if not args.window:
            Gdk.Display.get_default().get_monitors().connect(
                "items-changed", lambda *a: GLib.timeout_add(1500, build))
        GLib.timeout_add(int(1000 / FPS), tick)
        if hypr and hypr.available:
            refresh_visibility()
            events = hypr.open_events()
            if events:
                GLib.io_add_watch(events.fileno(), GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN, on_hypr_event)
            GLib.timeout_add_seconds(3, refresh_visibility)
        GLib.timeout_add_seconds(5, check_config)
        try:
            gi.require_version("GLibUnix", "2.0")
            from gi.repository import GLibUnix
            signal_add = GLibUnix.signal_add
        except (ImportError, ValueError):
            signal_add = GLib.unix_signal_add
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: app.quit() or False)
        signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, disaster_now)

    app.connect("activate", activate)
    app.run([])


def main():
    ap = argparse.ArgumentParser(description="Babel live wallpaper")
    ap.add_argument("--window", action="store_true", help="run in a normal window")
    ap.add_argument("--snapshot", metavar="PNG", help="render one frame and exit")
    ap.add_argument("--disaster-now", action="store_true", help="trigger the disaster in the running wallpaper")
    ap.add_argument("--cycle", help="override the cycle length, e.g. 10m (not saved)")
    ap.add_argument("--monument", choices=list(MONUMENTS))
    ap.add_argument("--disaster", choices=list(DISASTERS), help="(snapshot) jump to this disaster")
    ap.add_argument("--progress", type=float, default=0.7, help="(snapshot) build progress 0..1")
    ap.add_argument("--at", type=float, default=6.0, help="(snapshot) seconds to simulate first")
    ap.add_argument("--hour", type=float, help="force the time of day, e.g. 19.2")
    ap.add_argument("--weather", choices=["live", "off", "clear", "rain", "snow", "storm", "fog"],
                    help="(snapshot) pin the weather")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scale", type=int, default=2, help="(snapshot) output scale")
    args = ap.parse_args()
    if args.disaster_now:
        pids = running_pids()
        for pid in pids:
            os.kill(pid, signal.SIGUSR1)
        print("disaster triggered" if pids else "babel-live is not running")
        return
    if args.snapshot:
        snapshot(args)
    else:
        run_gtk(args)


if __name__ == "__main__":
    main()
