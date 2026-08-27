import os, re, json, urllib.request
from datetime import datetime, timezone

URL = os.environ["ICLOUD_CALENDAR_URL"].strip()

if URL.startswith("webcal://"):
    URL = "https://" + URL[len("webcal://"):]
elif URL.startswith("webcals://"):
    URL = "https://" + URL[len("webcals://"):]
OUT = "calendar.json"

def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)

def parse_dt(value):
    value = value.strip()
    if "T" not in value:
        return value[:4] + "-" + value[4:6] + "-" + value[6:8] + "T00:00:00"
    base = value.rstrip("Z")
    dt = datetime.strptime(base, "%Y%m%dT%H%M%S")
    return dt.isoformat()

def parse_events(text):
    text = unfold(text)
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
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
        events.append({
            "title": fields.get("SUMMARY", [""])[0],
            "start": parse_dt(start),
            "end": parse_dt(end),
            "location": fields.get("LOCATION", [""])[0],
        })
    return sorted(events, key=lambda x: x["start"])

with urllib.request.urlopen(URL, timeout=30) as r:
    raw = r.read().decode("utf-8-sig", errors="replace")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"updatedAt": datetime.now(timezone.utc).isoformat(), "events": parse_events(raw)},
              f, ensure_ascii=False, indent=2)
print(f"Wrote {OUT}")
