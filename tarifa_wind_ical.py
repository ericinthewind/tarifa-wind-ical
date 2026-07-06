#!/usr/bin/env python3
"""
Generate an iCalendar (.ics) feed with the best wind windows for Tarifa.

Data source: Open-Meteo Forecast API + Marine API.
No API key and no third-party Python packages required.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# -----------------------------------------------------------------------------
# Configuration via environment variables
# -----------------------------------------------------------------------------
SPOT_NAME = os.getenv("SPOT_NAME", "Tarifa")
LATITUDE = float(os.getenv("LATITUDE", "36.0143"))
LONGITUDE = float(os.getenv("LONGITUDE", "-5.6044"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")
FORECAST_DAYS = int(os.getenv("FORECAST_DAYS", "7"))
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "tarifa-wind.ics")
CALENDAR_NAME = os.getenv("CALENDAR_NAME", f"{SPOT_NAME} Wind Forecast")

# Profiles: kite, wingfoil, windsurf, custom.
PROFILE = os.getenv("PROFILE", "kite").lower().strip()

PROFILE_DEFAULTS = {
    "kite": {
        "MIN_WIND_KT": 16,
        "GOOD_WIND_KT": 20,
        "EXCELLENT_WIND_KT": 25,
        "MAX_GUST_KT": 40,
        "MAX_WAVE_M": 1.8,
        "MIN_BLOCK_HOURS": 2,
    },
    "wingfoil": {
        "MIN_WIND_KT": 12,
        "GOOD_WIND_KT": 16,
        "EXCELLENT_WIND_KT": 22,
        "MAX_GUST_KT": 38,
        "MAX_WAVE_M": 2.2,
        "MIN_BLOCK_HOURS": 2,
    },
    "windsurf": {
        "MIN_WIND_KT": 18,
        "GOOD_WIND_KT": 24,
        "EXCELLENT_WIND_KT": 30,
        "MAX_GUST_KT": 45,
        "MAX_WAVE_M": 2.0,
        "MIN_BLOCK_HOURS": 2,
    },
    "custom": {},
}

def default(name: str, fallback: float | int) -> str:
    return str(PROFILE_DEFAULTS.get(PROFILE, PROFILE_DEFAULTS["kite"]).get(name, fallback))

MIN_WIND_KT = float(os.getenv("MIN_WIND_KT", default("MIN_WIND_KT", 16)))
GOOD_WIND_KT = float(os.getenv("GOOD_WIND_KT", default("GOOD_WIND_KT", 20)))
EXCELLENT_WIND_KT = float(os.getenv("EXCELLENT_WIND_KT", default("EXCELLENT_WIND_KT", 25)))
MAX_GUST_KT = float(os.getenv("MAX_GUST_KT", default("MAX_GUST_KT", 40)))
MAX_WAVE_M = float(os.getenv("MAX_WAVE_M", default("MAX_WAVE_M", 1.8)))
MIN_BLOCK_HOURS = int(os.getenv("MIN_BLOCK_HOURS", default("MIN_BLOCK_HOURS", 2)))

# Levante roughly E/ENE/ESE, Poniente roughly W/WSW/WNW.
# Set WIND_SECTORS="0-360" to accept all wind directions.
WIND_SECTORS = os.getenv("WIND_SECTORS", "60-130,240-300")

# Events below this score are skipped. Set to 0 to include all usable sessions.
MIN_SCORE = int(os.getenv("MIN_SCORE", "35"))

# -----------------------------------------------------------------------------
# Models and helpers
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Hour:
    time: datetime
    wind_kt: float | None
    gust_kt: float | None
    direction_deg: float | None
    wave_m: float | None
    wave_period_s: float | None
    wave_direction_deg: float | None

@dataclass(frozen=True)
class Session:
    hours: list[Hour]
    score: int
    level: str
    emoji: str
    wind_name: str


def kt(kmh: float | None) -> float | None:
    return None if kmh is None else kmh * 0.539957


def parse_sectors(raw: str) -> list[tuple[float, float]]:
    sectors: list[tuple[float, float]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        start, end = part.split("-")
        sectors.append((float(start) % 360, float(end) % 360))
    return sectors


def direction_in_sectors(deg: float | None, sectors: list[tuple[float, float]]) -> bool:
    if deg is None:
        return False
    d = deg % 360
    for start, end in sectors:
        if start <= end and start <= d <= end:
            return True
        if start > end and (d >= start or d <= end):
            return True
    return False


def compass(deg: float | None) -> str:
    if deg is None:
        return "?"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int((deg + 11.25) // 22.5) % 16]


def wind_name(deg: float | None) -> str:
    if deg is None:
        return "Unknown"
    d = deg % 360
    if 45 <= d <= 135:
        return "Levante"
    if 225 <= d <= 315:
        return "Poniente"
    return compass(d)


def average(values: list[float | None]) -> float:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def fetch_json(base_url: str, params: dict[str, str | int | float]) -> dict:
    url = base_url + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_forecast() -> dict:
    return fetch_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
            "wind_speed_unit": "kmh",
            "timezone": TIMEZONE,
            "forecast_days": FORECAST_DAYS,
        },
    )


def fetch_marine() -> dict:
    return fetch_json(
        "https://marine-api.open-meteo.com/v1/marine",
        {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "hourly": "wave_height,wave_period,wave_direction",
            "timezone": TIMEZONE,
            "forecast_days": min(FORECAST_DAYS, 8),
        },
    )


def merge_hours(weather: dict, marine: dict) -> list[Hour]:
    tz = ZoneInfo(TIMEZONE)
    w = weather["hourly"]
    m = marine.get("hourly", {})
    marine_by_time = {t: i for i, t in enumerate(m.get("time", []))}
    out: list[Hour] = []

    for i, t in enumerate(w["time"]):
        mi = marine_by_time.get(t)
        dt = datetime.fromisoformat(t).replace(tzinfo=tz)
        out.append(
            Hour(
                time=dt,
                wind_kt=kt(w.get("wind_speed_10m", [None])[i]),
                gust_kt=kt(w.get("wind_gusts_10m", [None])[i]),
                direction_deg=w.get("wind_direction_10m", [None])[i],
                wave_m=m.get("wave_height", [None] * len(marine_by_time))[mi] if mi is not None else None,
                wave_period_s=m.get("wave_period", [None] * len(marine_by_time))[mi] if mi is not None else None,
                wave_direction_deg=m.get("wave_direction", [None] * len(marine_by_time))[mi] if mi is not None else None,
            )
        )
    return out


def is_usable(h: Hour) -> bool:
    return (
        h.wind_kt is not None
        and h.gust_kt is not None
        and h.wind_kt >= MIN_WIND_KT
        and h.gust_kt <= MAX_GUST_KT
        and direction_in_sectors(h.direction_deg, parse_sectors(WIND_SECTORS))
        and (h.wave_m is None or h.wave_m <= MAX_WAVE_M)
    )


def build_raw_blocks(hours: list[Hour]) -> list[list[Hour]]:
    blocks: list[list[Hour]] = []
    current: list[Hour] = []
    for h in hours:
        if is_usable(h):
            current.append(h)
        else:
            if len(current) >= MIN_BLOCK_HOURS:
                blocks.append(current)
            current = []
    if len(current) >= MIN_BLOCK_HOURS:
        blocks.append(current)
    return blocks


def score_block(block: list[Hour]) -> int:
    avg_wind = average([h.wind_kt for h in block])
    max_gust = max((h.gust_kt or 0) for h in block)
    max_wave = max((h.wave_m or 0) for h in block)
    duration = len(block)

    wind_score = min(60, max(0, int((avg_wind - MIN_WIND_KT) / max(1, EXCELLENT_WIND_KT - MIN_WIND_KT) * 60)))
    duration_score = min(20, duration * 5)
    gust_penalty = max(0, int((max_gust - EXCELLENT_WIND_KT - 8) * 2))
    wave_penalty = max(0, int((max_wave - 1.2) * 12))
    return max(0, min(100, wind_score + duration_score + 20 - gust_penalty - wave_penalty))


def classify(score: int, avg_wind: float) -> tuple[str, str]:
    if score >= 75 or avg_wind >= EXCELLENT_WIND_KT:
        return "Excellent", "🟢"
    if score >= 55 or avg_wind >= GOOD_WIND_KT:
        return "Good", "🟡"
    return "Possible", "⚪"


def build_sessions(hours: list[Hour]) -> list[Session]:
    sessions: list[Session] = []
    for block in build_raw_blocks(hours):
        score = score_block(block)
        if score < MIN_SCORE:
            continue
        avg_dir = average([h.direction_deg for h in block])
        avg_wind = average([h.wind_kt for h in block])
        level, emoji = classify(score, avg_wind)
        sessions.append(Session(block, score, level, emoji, wind_name(avg_dir)))
    return sessions


def ical_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fold_ical_line(line: str) -> str:
    # RFC 5545 line folding should be octet-based; this conservative character
    # folding is sufficient for this mostly ASCII feed.
    max_len = 73
    if len(line) <= max_len:
        return line
    parts = [line[:max_len]]
    line = line[max_len:]
    while line:
        parts.append(" " + line[:max_len])
        line = line[max_len:]
    return "\r\n".join(parts)


def make_calendar(sessions: list[Session]) -> str:
    now = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//tarifa-wind-ical//open-meteo//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ical_escape(CALENDAR_NAME)}",
        f"X-WR-TIMEZONE:{TIMEZONE}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]

    for session in sessions:
        block = session.hours
        start = block[0].time
        end = block[-1].time + timedelta(hours=1)
        avg_wind = average([h.wind_kt for h in block])
        max_gust = max((h.gust_kt or 0) for h in block)
        avg_dir = average([h.direction_deg for h in block])
        max_wave = max((h.wave_m or 0) for h in block)
        avg_period = average([h.wave_period_s for h in block])

        title = f"{session.emoji} {session.level} {session.wind_name}: {avg_wind:.0f} kt {compass(avg_dir)} · score {session.score}"
        desc = (
            f"Open-Meteo forecast for {SPOT_NAME}.\n"
            f"Profile: {PROFILE}.\n"
            f"Wind: {avg_wind:.1f} kt average, gusts up to {max_gust:.1f} kt.\n"
            f"Direction: {session.wind_name} ({compass(avg_dir)} / {avg_dir:.0f}°).\n"
            f"Waves: max {max_wave:.1f} m, period ~{avg_period:.0f} s.\n"
            f"Score: {session.score}/100.\n"
            f"Criteria: wind ≥ {MIN_WIND_KT:g} kt, gusts ≤ {MAX_GUST_KT:g} kt, waves ≤ {MAX_WAVE_M:g} m, sectors {WIND_SECTORS}."
        )
        uid = f"tarifa-{start.strftime('%Y%m%dT%H%M')}-{PROFILE}-{session.score}@tarifa-wind-ical"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{fmt_dt(now)}",
            f"DTSTART:{fmt_dt(start)}",
            f"DTEND:{fmt_dt(end)}",
            f"SUMMARY:{ical_escape(title)}",
            f"DESCRIPTION:{ical_escape(desc)}",
            f"LOCATION:{ical_escape(SPOT_NAME)}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_ical_line(line) for line in lines) + "\r\n"


def main() -> None:
    weather = fetch_forecast()
    marine = fetch_marine()
    hours = merge_hours(weather, marine)
    sessions = build_sessions(hours)
    calendar = make_calendar(sessions)

    output_dir = os.path.dirname(OUTPUT_FILE)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        f.write(calendar)

    print(f"Wrote {OUTPUT_FILE} with {len(sessions)} forecast events")
    for s in sessions:
        start = s.hours[0].time.strftime("%Y-%m-%d %H:%M")
        end = (s.hours[-1].time + timedelta(hours=1)).strftime("%H:%M")
        avg_wind = average([h.wind_kt for h in s.hours])
        print(f"- {start}-{end}: {s.emoji} {s.level} {s.wind_name}, {avg_wind:.0f} kt, score {s.score}")


if __name__ == "__main__":
    main()
