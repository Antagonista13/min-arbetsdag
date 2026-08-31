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
    """
    Kalenderfiler kan innehålla radbrytningar mitt i en rad.
    Dessa ska slås ihop enligt iCalendar-standarden.
    """
    return re.sub(r"\r?\n[ \t]", "", text)


def parse_dt(value):
    """
    Omvandlar iCalendar-datum till ISO-format.
    Klarar både heldagshändelser och händelser med tid.
    """
    value = value.strip()

    # Heldagshändelse
    if "T" not in value:
        try:
            dt = datetime.strptime(value[:8], "%Y%m%d")
            return dt.isoformat()
        except ValueError:
            return value

    # UTC-markering
    is_utc = value.endswith("Z")
    base = value.rstrip("Z")

    formats = [
        "%Y%m%dT%H%M%S",
        "%Y%m%dT%H%M",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(base, fmt)

            if is_utc:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.isoformat()
        except ValueError:
            continue

    return value


def parse_iso(value):
    """
    Säker omvandling från ISO-sträng till datetime.
    """
    try:
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)

        return dt

    except Exception:
        return None


def parse_rrule(rule):
    """
    Gör om en RRULE-rad till en dictionary.

    Exempel:
    FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR
    """
    result = {}

    for part in rule.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.upper()] = value

    return result


def weekday_number(day):
    """
    iCalendar använder:
    MO TU WE TH FR SA SU

    Python använder:
    Monday = 0
    Sunday = 6
    """
    days = {
        "MO": 0,
        "TU": 1,
        "WE": 2,
        "TH": 3,
        "FR": 4,
        "SA": 5,
        "SU": 6,
    }

    return days.get(day)


def parse_until(value):
    """
    RRULE UNTIL kan vara datum eller datum + tid.
    """
    if not value:
        return None

    value = value.strip()

    try:
        if "T" not in value:
            return datetime.strptime(
                value[:8],
                "%Y%m%d"
            )

        value = value.rstrip("Z")

        return datetime.strptime(
            value,
            "%Y%m%dT%H%M%S"
        )

    except ValueError:
        return None


def generate_occurrences(start, end, rrule, today, max_date):
    """
    Skapar enskilda kalenderhändelser från återkommande RRULE.

    Stöd:
    - DAILY
    - WEEKLY
    - MONTHLY

    Samt:
    - INTERVAL
    - COUNT
    - UNTIL
    - BYDAY
    """

    rule = parse_rrule(rrule)

    frequency = rule.get("FREQ", "").upper()
    interval = int(rule.get("INTERVAL", "1"))

    count_limit = rule.get("COUNT")
    count_limit = int(count_limit) if count_limit else None

    until = parse_until(rule.get("UNTIL"))

    byday = [
        weekday_number(day.strip())
        for day in rule.get("BYDAY", "").split(",")
        if weekday_number(day.strip()) is not None
    ]

    occurrences = []

    duration = end - start

    if duration.total_seconds() < 0:
        duration = timedelta(0)

    current = start
    generated = 0

    # Skydd mot oändliga loopar
    safety_limit = 2000

    while generated < safety_limit:

        if count_limit and generated >= count_limit:
            break

        if until and current > until:
            break

        if current.date() > max_date:
            break

        should_add = False

        # -------------------------
        # DAGLIG
        # -------------------------
        if frequency == "DAILY":

            days_since_start = (
                current.date() - start.date()
            ).days

            if days_since_start % interval == 0:
                should_add = True

        # -------------------------
        # VECKOVIS
        # -------------------------
        elif frequency == "WEEKLY":

            days_since_start = (
                current.date() - start.date()
            ).days

            weeks_since_start = days_since_start // 7

            valid_week = (
                weeks_since_start % interval == 0
            )

            if valid_week:

                if byday:

                    if current.weekday() in byday:
                        should_add = True

                else:

                    if current.weekday() == start.weekday():
                        should_add = True

        # -------------------------
        # MÅNATLIG
        # -------------------------
        elif frequency == "MONTHLY":

            months_since_start = (
                (current.year - start.year) * 12
                + current.month
                - start.month
            )

            if (
                months_since_start >= 0
                and months_since_start % interval == 0
                and current.day == start.day
            ):
                should_add = True

        # Om frekvensen inte känns igen
        else:
            should_add = False

        if should_add:

            if current.date() >= today:

                occurrences.append({
                    "start": current.isoformat(),
                    "end": (current + duration).isoformat(),
                })

            generated += 1

        current += timedelta(days=1)

    return occurrences


def parse_events(text):

    text = unfold(text)

    events = []

    today = datetime.now().date()
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

            # Tar bort parametrar exempelvis:
            # DTSTART;TZID=Europe/Stockholm
            key = key.split(";", 1)[0].upper()

            fields.setdefault(key, []).append(
                value.strip()
            )

        if "DTSTART" not in fields:
            continue

        start_raw = fields["DTSTART"][0]

        end_raw = fields.get(
            "DTEND",
            [start_raw]
        )[0]

        parsed_start = parse_dt(start_raw)
        parsed_end = parse_dt(end_raw)

        start = parse_iso(parsed_start)
        end = parse_iso(parsed_end)

        if not start:
            continue

        if not end:
            end = start

        title = fields.get(
            "SUMMARY",
            [""]
        )[0]

        location = fields.get(
            "LOCATION",
            [""]
        )[0]

        rrule = fields.get(
            "RRULE",
            [None]
        )[0]

        # --------------------------------
        # ÅTERKOMMANDE HÄNDELSE
        # --------------------------------
        if rrule:

            occurrences = generate_occurrences(
                start,
                end,
                rrule,
                today,
                max_date
            )

            for occurrence in occurrences:

                events.append({
                    "title": title,
                    "start": occurrence["start"],
                    "end": occurrence["end"],
                    "location": location,
                })

        # --------------------------------
        # VANLIG HÄNDELSE
        # --------------------------------
        else:

            # Om en händelse sträcker sig över flera dagar
            # behåller vi den så länge den fortfarande är aktuell.
            if end.date() < today:
                continue

            if start.date() > max_date:
                continue

            events.append({
                "title": title,
                "start": parsed_start,
                "end": parsed_end,
                "location": location,
            })

    # Sortera kalendern
    events.sort(
        key=lambda x: x["start"]
    )

    return events


# ==========================
# HÄMTA ICLOUD-KALENDERN
# ==========================

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

with urllib.request.urlopen(
    request,
    timeout=30
) as response:

    raw_bytes = response.read()


# Försök först med UTF-8
try:
    raw = raw_bytes.decode(
        "utf-8-sig"
    )

except UnicodeDecodeError:

    raw = raw_bytes.decode(
        "latin-1"
    )


# ==========================
# SKAPA CALENDAR.JSON
# ==========================

events = parse_events(raw)

with open(
    OUT,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        {
            "updatedAt": datetime.now(
                timezone.utc
            ).isoformat(),

            "events": events,
        },
        file,
        ensure_ascii=False,
        indent=2,
    )


print(
    f"Wrote {OUT} with {len(events)} events"
)
