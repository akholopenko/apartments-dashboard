import json
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "dashboard_config.json"
REQUEST_TIMEOUT_SECONDS = 20


DEFAULT_CONFIG = {
    "apartments": [
        {
            "name": "Apartment 1",
            "ical_urls": [
                "https://ical.booking.com/v1/export/t/example.ics",
                "https://www.airbnb.es/calendar/ical/example.ics?t=token",
            ],
        }
    ],
    "request_timeout_seconds": 20,
}


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return DEFAULT_CONFIG

    with CONFIG_PATH.open("r", encoding="utf-8-sig") as f:
        config = json.load(f)

    if "apartments" not in config or not isinstance(config["apartments"], list):
        raise ValueError("Invalid config: 'apartments' list is required")

    return config


def unfold_ical_lines(data):
    unfolded = []
    for raw_line in data.splitlines():
        line = raw_line.rstrip("\r\n")
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def normalize_ical_date(raw_value):
    value = raw_value.strip()
    if "T" in value:
        value = value.split("T", 1)[0]
    return value[:8]


def parse_ical(data):
    events = []
    event = {}
    inside_event = False

    for line in unfold_ical_lines(data):
        if line == "BEGIN:VEVENT":
            inside_event = True
            event = {}
            continue

        if line == "END:VEVENT":
            inside_event = False
            if {"start", "end"} <= set(event.keys()):
                events.append(event)
            continue

        if not inside_event or ":" not in line:
            continue

        key, value = line.split(":", 1)
        field = key.split(";", 1)[0].upper()

        if field == "UID":
            event["uid"] = value.strip()
        elif field == "DTSTART":
            event["start"] = normalize_ical_date(value)
        elif field == "DTEND":
            event["end"] = normalize_ical_date(value)

    return events


def fetch_calendar(url, timeout_seconds):
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ApartmentsDashboard/1.0)",
            "Accept": "text/calendar,*/*;q=0.9",
        },
    )
    response.raise_for_status()
    return parse_ical(response.text)


def merge_ranges(ranges):
    if not ranges:
        return []

    ranges = sorted(ranges)
    merged = [[ranges[0][0], ranges[0][1]]]

    for start, end in ranges[1:]:
        _, last_end = merged[-1]
        if start <= last_end:
            merged[-1][1] = max(last_end, end)
        else:
            merged.append([start, end])

    return [(start, end) for start, end in merged]


def load_apartment_data(apartment, timeout_seconds):
    raw_ranges = []
    errors = []

    for url in apartment.get("ical_urls", []):
        try:
            events = fetch_calendar(url, timeout_seconds)
            for event in events:
                start = datetime.strptime(event["start"], "%Y%m%d").date()
                end = datetime.strptime(event["end"], "%Y%m%d").date()
                if end > start:
                    raw_ranges.append((start, end))
        except Exception as exc:
            errors.append((url, str(exc)))

    dedup_raw_ranges = sorted(set(raw_ranges))
    occupancy_ranges = merge_ranges(dedup_raw_ranges)
    return {
        "raw_ranges": dedup_raw_ranges,
        "occupancy_ranges": occupancy_ranges,
    }, errors


def is_occupied(ranges, day):
    for start, end in ranges:
        if start <= day < end:
            return True
    return False


def day_stats(apartments_data, day):
    checkins = []
    checkouts = []
    potential = []

    for apartment_name, apartment_data in apartments_data.items():
        raw_ranges = apartment_data["raw_ranges"]
        occupancy_ranges = apartment_data["occupancy_ranges"]

        has_checkin = any(start == day for start, _ in raw_ranges)
        has_checkout = any(end == day for _, end in raw_ranges)
        occupied_today = is_occupied(occupancy_ranges, day)
        occupied_yesterday = is_occupied(occupancy_ranges, day - timedelta(days=1))

        if has_checkin:
            checkins.append(apartment_name)
        if has_checkout:
            checkouts.append(apartment_name)

        if (not has_checkout) and (not occupied_today) and (not occupied_yesterday):
            potential.append(apartment_name)

    return checkins, checkouts, potential


def get_dashboard_data(days=21, start_date=None):
    if start_date is None:
        start_day = date.today()
    elif isinstance(start_date, str):
        start_day = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        start_day = start_date

    config = load_config()
    timeout_seconds = int(config.get("request_timeout_seconds", REQUEST_TIMEOUT_SECONDS))

    apartments_data = {}
    warnings = []

    for apartment in config["apartments"]:
        name = apartment.get("name", "Unnamed apartment")
        apartment_data, errors = load_apartment_data(apartment, timeout_seconds)
        apartments_data[name] = apartment_data
        for url, message in errors:
            warnings.append({"apartment": name, "url": url, "error": message})

    rows = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        checkins, checkouts, potential = day_stats(apartments_data, day)
        rows.append(
            {
                "date": day.isoformat(),
                "checkins_count": len(checkins),
                "checkouts_count": len(checkouts),
                "potential_count": len(potential),
                "checkins_apartments": checkins,
                "checkouts_apartments": checkouts,
                "potential_apartments": potential,
            }
        )

    return {
        "start_date": start_day.isoformat(),
        "days": days,
        "rows": rows,
        "warnings": warnings,
    }
