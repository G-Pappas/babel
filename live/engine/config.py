"""User settings (~/.config/babel-live/config.toml) and per-monitor saved state.

The file is rewritten in a fixed layout (one list item per line) so that the
Omarchy menu can show check marks with a plain grep.
"""

import json
import os
import re
import tomllib
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "babel-live" / "config.toml"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "babel-live"

WONDERS = {
    "eiffel": "Eiffel Tower", "parthenon": "Parthenon", "empire-state": "Empire State Building",
    "big-ben": "Big Ben", "taj-mahal": "Taj Mahal", "colosseum": "Colosseum",
    "opera-house": "Sydney Opera House", "burj-khalifa": "Burj Khalifa",
    "giza": "Great Pyramid of Giza", "hanging-gardens": "Hanging Gardens of Babylon",
    "temple-of-artemis": "Temple of Artemis", "statue-of-zeus": "Statue of Zeus",
    "mausoleum": "Mausoleum at Halicarnassus", "colossus": "Colossus of Rhodes",
    "lighthouse": "Lighthouse of Alexandria",
    "chichen-itza": "Chichen Itza", "stonehenge": "Stonehenge", "statue-of-liberty": "Statue of Liberty",
    "leaning-tower": "Leaning Tower of Pisa", "st-basils": "St. Basil's Cathedral", "petra": "Petra",
}
DISASTERS = {"kaiju": "Kaiju", "kraken": "Kraken", "dragon": "Dragon", "tripods": "Martian tripods",
             "giant-ape": "Giant ape", "ufo": "UFO", "space-battle": "Space battle"}
SKY_MODES = ("clock", "loop", "dawn", "day", "sunset", "night")
WEATHER_MODES = ("live", "off", "clear", "rain", "snow", "storm", "fog")
MONITOR_MODES = ("span", "separate")
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}

TEMPLATE = """\
# Babel live wallpaper settings. Changes are picked up within a few seconds.
# Easiest to change from the Omarchy menu: Style > Babel.

# How long one build-and-destroy cycle takes, e.g. "1m", "20m", "6h", "1d", "1w".
cycle = "{cycle}"

# Sky: "clock" follows the real time of day, "loop" runs a whole day and night
# every sky_loop, or pin it to "dawn", "day", "sunset" or "night".
sky = "{sky}"
sky_loop = "{sky_loop}"

# Weather: "live" uses the real weather where you are (the location Omarchy's
# weather widget uses), "off", or pin "clear", "rain", "snow", "storm" or "fog".
weather = "{weather}"

# Behind the scene: "live" for the drawn landscape, or the path of a picture.
background = {background}

# With several monitors: "span" makes them one wide scene, the wonder on one
# monitor and the crew's yard (container, campfire, stockyard) next to it;
# "separate" gives every monitor a wonder of its own.
monitors = "{monitors}"

# The monitor the wonder goes up on when spanning, e.g. "HDMI-A-1" (see
# `hyprctl monitors`). Empty: the biggest one.
wonder_monitor = {wonder_monitor}

# Smallest crew on each scene. Short cycles hire more workers (up to 40)
# and, if that is still not enough, the crew works in time-lapse.
workers = {workers}

# Which monuments get built, and which disasters may strike.
wonders = [
{wonders}
]
disasters = [
{disasters}
]
"""


def toml_str(text):
    """A TOML string: JSON's escaping is valid TOML, so quotes, backslashes and
    newlines in a path can't break out of the line."""
    return json.dumps(str(text), ensure_ascii=False)


def parse_duration(text):
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhdw])\s*", str(text))
    if not m:
        raise ValueError(f"bad duration {text!r} (use e.g. 30m, 6h, 1d, 1w)")
    return max(60.0, float(m.group(1)) * UNITS[m.group(2)])


class Config:
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self.mtime = None
        self.cycle_text = "1d"
        self.cycle = 86400.0
        self.sky = "clock"
        self.sky_loop_text = "10m"
        self.sky_loop = 600.0
        self.background = "live"
        self.weather = "live"
        self.workers = 9
        self.monitors = "span"
        self.wonder_monitor = ""
        self.wonders = list(WONDERS)
        self.disasters = list(DISASTERS)
        if not path.exists():
            self.save()
        self.reload()

    def reload(self):
        """Re-read the file if it changed; returns True when something changed."""
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return False
        if mtime == self.mtime:
            return False
        self.mtime = mtime
        try:
            data = tomllib.loads(self.path.read_text())
            text = str(data.get("cycle", "1d"))
            self.cycle, self.cycle_text = parse_duration(text), text
            sky = data.get("sky", "clock")
            self.sky = sky if sky in SKY_MODES else "clock"
            loop = str(data.get("sky_loop", "10m"))
            self.sky_loop, self.sky_loop_text = parse_duration(loop), loop
            self.background = str(data.get("background", "live")) or "live"
            weather = data.get("weather", "live")
            self.weather = weather if weather in WEATHER_MODES else "live"
            self.workers = max(2, min(30, int(data.get("workers", 9))))
            monitors = data.get("monitors", "span")
            self.monitors = monitors if monitors in MONITOR_MODES else "span"
            self.wonder_monitor = str(data.get("wonder_monitor", ""))
            wonders = [w for w in data.get("wonders", WONDERS) if w in WONDERS]
            renamed = {"starwars": "space-battle", "tsunami": "kraken", "tornado": "dragon",  # older settings
                       "meteor": "tripods", "earthquake": "giant-ape"}
            disasters = [renamed.get(d, d) for d in data.get("disasters", DISASTERS)]
            disasters = [d for d in disasters if d in DISASTERS]
            self.wonders = wonders or list(WONDERS)
            self.disasters = disasters or list(DISASTERS)
        except (ValueError, TypeError, tomllib.TOMLDecodeError) as e:
            print(f"babel-live: ignoring config error: {e}")
        return True

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = TEMPLATE.format(
            cycle=self.cycle_text, sky=self.sky, sky_loop=self.sky_loop_text, workers=self.workers,
            weather=self.weather, monitors=self.monitors, wonder_monitor=toml_str(self.wonder_monitor),
            background=toml_str(self.background),
            wonders="\n".join(f'  "{w}",' for w in WONDERS if w in self.wonders),
            disasters="\n".join(f'  "{d}",' for d in DISASTERS if d in self.disasters))
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(text)
        tmp.replace(self.path)
        self.mtime = None


def _state_file(key):
    return STATE_DIR / (re.sub(r"[^A-Za-z0-9_-]", "_", key) + ".json")


def load_state(key):
    try:
        return json.loads(_state_file(key).read_text())
    except (OSError, ValueError):
        return None


def save_state(key, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_file(key).write_text(json.dumps(state))
