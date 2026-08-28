import os
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta

URL = os.environ["ICLOUD_CALENDAR_URL"]
OUT = "calendar.json"

# Hur långt framåt kalendern ska hämtas
DAYS_AHEAD = 90


def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def parse_dt(value):
    value = value.strip()

    if "T" not in value:
        return (
            value[0:4]
            + "-"
            + value[4:6]
            + "-"
            + value[6:8]
            + "T00:00:00"
        )

    base = value.rstrip("Z")

    try:
        dt = datetime.strptime(base, "%Y%m%dT%H%M%S")
        return dt.isoformat()
    except ValueError:
        return value


def parse_events(text):
    text = unfold(text)
    events = []

    today = datetime.now(timezone.utc).date()
    max_date = today + timedelta(days=DAYS_AHEAD)

    for block in re.findall(
        r"BEGIN:VEVENT(.*?)END:VEVENT",
        text,
        re.S
    ):
        fields = {}

        for line in block.splitlines():
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.split(";", 1)[0].upper()

            fields.setdefault(key, []).append(value.strip())

        if "DTSTART" not in fields:
            continue

        start = fields["DTSTART"][0]
        end = fields.get("DTEND", [start])[0]

        parsed_start = parse_dt(start)
        parsed_end = parse_dt(end)

        try:
            start_dt = datetime.fromisoformat(parsed_start)
            end_dt = datetime.fromisoformat(parsed_end)
        except ValueError:
            continue

        # Heldagsevent i iCalendar använder datumformat (VALUE=DATE)
        # och DTEND är normalt exklusivt, dvs. en händelse
        # 20260915 -> 20260919 täcker 15-18 september.
        all_day = "T" not in start

        # Behåll händelser som överlappar vårt tidsfönster.
        # Detta är viktigt för fler-dagars-/veckohändelser som
        # startade före idag men fortfarande pågår.
        if end_dt.date() <= today:
            continue

        if start_dt.date() > max_date:
            continue

        events.append({
            "title": fields.get("SUMMARY", [""])[0],
            "start": parsed_start,
            "end": parsed_end,
            "location": fields.get("LOCATION", [""])[0],
            "allDay": all_day,
        })

    return sorted(
        events,
        key=lambda x: x["start"]
    )


URL = URL.strip()

if URL.lower().startswith("webcal://"):
    URL = "https://" + URL[9:]

request = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/calendar,text/plain,*/*",
    },
)

with urllib.request.urlopen(request, timeout=30) as r:
    raw_bytes = r.read()

# Försök först med UTF-8. Om kalendern innehåller äldre
# teckenkodning använder vi latin-1 som reserv istället
# för att förstöra tecken med �.
try:
    raw = raw_bytes.decode("utf-8-sig")
except UnicodeDecodeError:
    raw = raw_bytes.decode("latin-1")

with open(
    OUT,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        {
            "updatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "events": parse_events(raw),
        },
        f,
        ensure_ascii=False,
        indent=2,
    )

print(f"Wrote {OUT}")
