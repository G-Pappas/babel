"""Where the sun and moon are, for a place and a moment (low-precision formulas,
good to a degree or so - plenty for a wallpaper).

Angles in degrees; azimuth is measured from north, clockwise.
"""

import json
import math
from pathlib import Path

OMARCHY_LOCATION = Path.home() / ".local/state/omarchy/settings/weather.json"
WEATHER_CACHE = Path.home() / ".cache/babel-live/weather.json"
_rad, _deg = math.radians, math.degrees


def location():
    """(lat, lon) from Omarchy's weather location, or from the last weather lookup."""
    for path in (OMARCHY_LOCATION, WEATHER_CACHE):
        try:
            d = json.loads(path.read_text())
            if d.get("latitude") is not None and d.get("longitude") is not None:
                return float(d["latitude"]), float(d["longitude"])
        except (OSError, ValueError, TypeError):
            pass
    return None


def _days(t):
    return t / 86400.0 + 2440587.5 - 2451545.0  # days since J2000


def _alt_az(ra, dec, t, lat, lon):
    gmst = (280.46061837 + 360.98564736629 * _days(t)) % 360
    ha = _rad((gmst + lon - ra) % 360)
    lat_r, dec_r = _rad(lat), _rad(dec)
    alt = math.asin(math.sin(lat_r) * math.sin(dec_r) + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha))
    az = math.atan2(math.sin(ha), math.cos(ha) * math.sin(lat_r) - math.tan(dec_r) * math.cos(lat_r))
    return _deg(alt), (_deg(az) + 180) % 360, math.sin(ha) < 0  # rising: before it crosses the meridian


def _ecliptic_to_equatorial(lam, beta, d):
    eps = _rad(23.439 - 0.0000004 * d)
    lam, beta = _rad(lam), _rad(beta)
    ra = math.atan2(math.sin(lam) * math.cos(eps) - math.tan(beta) * math.sin(eps), math.cos(lam))
    dec = math.asin(math.sin(beta) * math.cos(eps) + math.cos(beta) * math.sin(eps) * math.sin(lam))
    return _deg(ra) % 360, _deg(dec)


def sun_longitude(t):
    d = _days(t)
    g = _rad(357.529 + 0.98560028 * d)
    return (280.459 + 0.98564736 * d + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360


def sun(t, lat, lon):
    """(altitude, azimuth, rising)."""
    ra, dec = _ecliptic_to_equatorial(sun_longitude(t), 0.0, _days(t))
    return _alt_az(ra, dec, t, lat, lon)


def moon(t, lat, lon):
    """(altitude, azimuth, lit fraction 0..1)."""
    d = _days(t)
    lam = 218.316 + 13.176396 * d + 6.289 * math.sin(_rad(134.963 + 13.064993 * d))
    beta = 5.128 * math.sin(_rad(93.272 + 13.229350 * d))
    ra, dec = _ecliptic_to_equatorial(lam % 360, beta, d)
    alt, az, _ = _alt_az(ra, dec, t, lat, lon)
    elongation = _rad((lam - sun_longitude(t)) % 360)
    return alt, az, (1 - math.cos(elongation)) / 2


def equivalent_hour(alt, rising, noon_alt):
    """Map the sun's height to the hour of the stylised day the sky colours are keyed on."""
    def lerp(a, b, k):
        return a + (b - a) * max(0.0, min(1.0, k))
    if rising:
        if alt <= -18:
            return 3.0
        if alt <= -6:
            return lerp(4.8, 5.8, (alt + 18) / 12)
        if alt <= 0:
            return lerp(5.8, 6.3, (alt + 6) / 6)
        if alt <= 10:
            return lerp(6.3, 8.0, alt / 10)
        return lerp(8.0, 13.0, (alt - 10) / max(1.0, noon_alt - 10))
    if alt >= 10:
        return lerp(13.0, 17.3, (noon_alt - alt) / max(1.0, noon_alt - 10))
    if alt >= 0:
        return lerp(17.3, 19.2, (10 - alt) / 10)
    if alt >= -6:
        return lerp(19.2, 20.4, -alt / 6)
    if alt >= -18:
        return lerp(20.4, 21.8, (-alt - 6) / 12)
    return 23.0


def noon_altitude(t, lat):
    ra, dec = _ecliptic_to_equatorial(sun_longitude(t), 0.0, _days(t))
    return 90 - abs(lat - dec)
