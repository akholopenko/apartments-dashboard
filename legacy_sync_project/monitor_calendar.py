import json
import logging
import os
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

import requests


DEFAULT_CONFIG = {
    "ical_urls": [
        "https://ical.booking.com/v1/export/t/149901f1-37ab-4fda-bcb9-1f871d74e5e6.ics",
        "https://www.airbnb.es/calendar/ical/1380914254871656267.ics?t=485622702244431ba985547bb50dda6f",
    ],
    "max_stay_days": 90,
    "request_timeout_seconds": 20,
}
CONFIG_PATH = "config.json"
LOG_PATH = "monitor.log"


def setup_logging():
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger("monitor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def load_events():
    if os.path.exists("events.json"):
        with open("events.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_events(events):
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(events, f)


def get_last_request():
    if os.path.exists("last_request.txt"):
        with open("last_request.txt", "r", encoding="utf-8") as f:
            value = f.read().strip()
            if value:
                return float(value)
    return 0


def load_config():
    config = dict(DEFAULT_CONFIG)

    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"Config created: {CONFIG_PATH}")
        return config

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw_config = json.load(f)
    except Exception as e:
        print(f"Cannot read {CONFIG_PATH}, using defaults.")
        print(e)
        return config

    if isinstance(raw_config.get("ical_urls"), list):
        urls = [url for url in raw_config["ical_urls"] if isinstance(url, str) and url.strip()]
        if urls:
            config["ical_urls"] = urls

    if isinstance(raw_config.get("max_stay_days"), int) and raw_config["max_stay_days"] >= 0:
        config["max_stay_days"] = raw_config["max_stay_days"]

    if (
        isinstance(raw_config.get("request_timeout_seconds"), (int, float))
        and raw_config["request_timeout_seconds"] > 0
    ):
        config["request_timeout_seconds"] = raw_config["request_timeout_seconds"]

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
            if {"uid", "start", "end"} <= set(event.keys()):
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


def detect_conflicts(events):
    conflicts = []
    items = list(events.items())

    for i in range(len(items)):
        uid1, (start1, end1) = items[i]
        source1 = uid1.split("_", 1)[0]
        s1 = datetime.strptime(start1, "%Y%m%d")
        e1 = datetime.strptime(end1, "%Y%m%d")

        for j in range(i + 1, len(items)):
            uid2, (start2, end2) = items[j]
            source2 = uid2.split("_", 1)[0]

            if source1 == source2:
                continue

            s2 = datetime.strptime(start2, "%Y%m%d")
            e2 = datetime.strptime(end2, "%Y%m%d")

            if s1 < e2 and s2 < e1:
                overlap_start = max(s1, s2)
                overlap_end = min(e1, e2)
                conflicts.append((uid1, uid2, overlap_start, overlap_end))

    return conflicts


def merge_ranges(events):
    ranges = []
    for start, end in events.values():
        start_date = datetime.strptime(start, "%Y%m%d")
        end_date = datetime.strptime(end, "%Y%m%d")
        ranges.append((start_date, end_date))

    ranges.sort()
    merged = []

    for start, end in ranges:
        if not merged:
            merged.append([start, end])
            continue

        _, last_end = merged[-1]
        if start <= last_end:
            merged[-1][1] = max(last_end, end)
        else:
            merged.append([start, end])

    return merged


def generate_ics(events):
    merged = merge_ranges(events)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "PRODID:-//SyncApp//EN",
    ]

    for start, end in merged:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:sync_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}@sync")
        lines.append("DTSTAMP:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
        lines.append("SUMMARY:BLOCKED")
        lines.append("STATUS:CONFIRMED")
        lines.append("TRANSP:OPAQUE")
        lines.append("SEQUENCE:0")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    with open("synced_calendar.ics", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def detect_source(url):
    url_lower = url.lower()
    if "booking" in url_lower:
        return "booking"
    if "airbnb" in url_lower:
        return "airbnb"
    return "unknown"


def fetch_calendar(url):
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; iCalSync/1.0)",
            "Accept": "text/calendar,*/*;q=0.9",
        },
    )
    response.raise_for_status()
    return parse_ical(response.text)


known_events = load_events()
config = load_config()
ICAL_URLS = config["ical_urls"]
MAX_STAY_DAYS = config["max_stay_days"]
REQUEST_TIMEOUT_SECONDS = config["request_timeout_seconds"]
logger = setup_logging()

while True:
    try:
        latest_events = {}
        current_uids_by_source = {}
        successful_sources = set()

        for url in ICAL_URLS:
            source = detect_source(url)
            try:
                parsed = fetch_calendar(url)
                logger.info("Calendar loaded: %s", url)
                logger.info("Events parsed: %s", len(parsed))

                successful_sources.add(source)
                current_uids_by_source.setdefault(source, set())

                for event in parsed:
                    uid = f"{source}_{event['uid']}"
                    start = event["start"]
                    end = event["end"]

                    start_date = datetime.strptime(start, "%Y%m%d")
                    end_date = datetime.strptime(end, "%Y%m%d")
                    length = (end_date - start_date).days

                    if length <= 0:
                        continue

                    # 0 means unlimited duration filter (do not cut long technical blocks).
                    if MAX_STAY_DAYS > 0 and length > MAX_STAY_DAYS:
                        continue

                    latest_events[uid] = [start, end]
                    current_uids_by_source[source].add(uid)

            except Exception as e:
                logger.exception("Error loading calendar: %s", url)
                if isinstance(e, requests.HTTPError) and e.response is not None:
                    if source == "booking" and e.response.status_code in (400, 401, 403, 410):
                        logger.warning(
                            "Booking iCal link looks invalid or expired. "
                            "Generate a new private URL in Booking and update config.json."
                        )

        for uid, (start, end) in latest_events.items():
            if uid not in known_events:
                logger.info("New booking detected: uid=%s check-in=%s check-out=%s", uid, start, end)
            else:
                old_start, old_end = known_events[uid]
                if old_start != start or old_end != end:
                    logger.info(
                        "Updated booking: uid=%s old=%s-%s new=%s-%s",
                        uid,
                        old_start,
                        old_end,
                        start,
                        end,
                    )

            known_events[uid] = [start, end]

        for uid in list(known_events.keys()):
            source = uid.split("_", 1)[0]
            if source not in successful_sources:
                continue

            source_current_uids = current_uids_by_source.get(source, set())
            if uid not in source_current_uids:
                logger.info("Cancelled booking: uid=%s", uid)
                del known_events[uid]

    except Exception as e:
        logger.exception("Unexpected monitor loop error")

    conflicts = detect_conflicts(known_events)

    if conflicts:
        logger.warning("Possible overbooking detected")
        for uid1, uid2, overlap_start, overlap_end in conflicts:
            logger.warning(
                "Conflict: %s vs %s, nights %s to %s",
                uid1.split("_", 1)[0],
                uid2.split("_", 1)[0],
                overlap_start.strftime("%Y-%m-%d"),
                overlap_end.strftime("%Y-%m-%d"),
            )

    generate_ics(known_events)
    save_events(known_events)
    logger.info("ICS file updated")

    last_request = get_last_request()
    if time.time() - last_request < 20:
        interval = 3
    else:
        interval = 30

    logger.info("Next refresh in %s seconds", interval)
    time.sleep(interval)
