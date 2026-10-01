"""Live weather for the scene, from Open-Meteo (free, no API key).

The location is the one Omarchy's own weather widget uses
(~/.local/state/omarchy/settings/weather.json); without it the city is guessed
from the IP address, the same way the widget does. Fetching runs on a
background thread every 20 minutes and is cached, so the scene never waits.
"""

import json
import math
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

OMARCHY_LOCATION = Path.home() / ".local/state/omarchy/settings/weather.json"
CACHE = Path.home() / ".cache/babel-live/weather.json"
REFRESH = 20 * 60
FORCED = {  # weather setting -> what to show, for when the user pins it
    "clear": {"kind": "clear", "amount": 0.0, "cloud": 0.1},
    "rain": {"kind": "rain", "amount": .7, "cloud": .8},
    "snow": {"kind": "snow", "amount": .7, "cloud": .7},
    "storm": {"kind": "storm", "amount": 1.0, "cloud": 1.0},
    "fog": {"kind": "fog", "amount": .8, "cloud": .6},
}
CALM = {"kind": "clear", "amount": 0.0, "cloud": 0.0, "wind": 0.0}


def from_wmo(code, cloud_cover, wind_kmh, wind_dir):
    """Turn an Open-Meteo current report into what the scene draws."""
    cloud = (cloud_cover or 0) / 100
    kind, amount = "clear", 0.0
    if code in (45, 48):
        kind, amount = "fog", .8
    elif 51 <= code <= 57:
        kind, amount = "rain", .3
    elif code in (61, 80):
        kind, amount = "rain", .45
    elif code in (63, 66, 81):
        kind, amount = "rain", .7
    elif code in (65, 67, 82):
        kind, amount = "rain", 1.0
    elif code in (71, 85, 77):
        kind, amount = "snow", .4
    elif code in (73,):
        kind, amount = "snow", .7
    elif code in (75, 86):
        kind, amount = "snow", 1.0
    elif code >= 95:
        kind, amount = "storm", 1.0
    elif code == 3:
        cloud = max(cloud, .85)
    # wind blowing *from* wind_dir degrees; + means it pushes things to the right
    wind = -math.sin(math.radians(wind_dir or 0)) * min(1.0, (wind_kmh or 0) / 50)
    return {"kind": kind, "amount": amount, "cloud": cloud, "wind": wind}


class Weather:
    def __init__(self, config):
        self.config = config
        self.live = dict(CALM)
        self.place = ""
        self.fetched = 0.0
        self.busy = False
        try:
            cached = json.loads(CACHE.read_text())
            self.live, self.place, self.fetched = cached["live"], cached.get("place", ""), cached["time"]
        except (OSError, ValueError, KeyError):
            pass

    def current(self):
        """What to draw right now."""
        mode = getattr(self.config, "weather", "live")
        if mode == "off":
            return dict(CALM)
        if mode in FORCED:
            return dict(FORCED[mode], wind=.3)
        if time.time() - self.fetched > REFRESH and not self.busy:
            self.busy = True
            threading.Thread(target=self._fetch, daemon=True).start()
        return self.live

    # ---- network (background thread) ----
    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "babel-live (Omarchy theme)"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode()

    def _location(self):
        try:
            loc = json.loads(OMARCHY_LOCATION.read_text())
            if loc.get("latitude") is not None and loc.get("longitude") is not None:
                return float(loc["latitude"]), float(loc["longitude"]), loc.get("name", "")
            name = loc.get("name", "")
        except (OSError, ValueError, TypeError):
            name = self._get("https://wttr.in/?format=%l").split(",")[0].strip()
        if not name:
            return None
        found = json.loads(self._get("https://geocoding-api.open-meteo.com/v1/search?count=1&name="
                                     + urllib.parse.quote(name)))
        hit = (found.get("results") or [None])[0]
        return (hit["latitude"], hit["longitude"], hit.get("name", name)) if hit else None

    def _fetch(self):
        try:
            loc = self._location()
            if loc:
                lat, lon, place = loc
                data = json.loads(self._get(
                    "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                    "&current=weather_code,cloud_cover,wind_speed_10m,wind_direction_10m" % (lat, lon)))
                cur = data["current"]
                self.live = from_wmo(cur["weather_code"], cur.get("cloud_cover"),
                                     cur.get("wind_speed_10m"), cur.get("wind_direction_10m"))
                self.place = place
                self.fetched = time.time()
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps({"live": self.live, "place": place, "time": self.fetched,
                                             "code": cur["weather_code"]}))
        except Exception as e:  # offline, timeouts, odd answers: keep the last report
            print(f"babel-live: weather unavailable ({e})")
            self.fetched = time.time() - REFRESH + 300  # try again in five minutes
        finally:
            self.busy = False
