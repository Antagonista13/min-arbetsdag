import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

DISTRIBUTOR_ID = "68d18b0e30b565aba61bf59e"

API_URL = "https://menu.matildaplatform.com/api/menu"

OUTPUT_FILE = "menu.json"


def fetch_menu():
    print("Hämtar matsedel från Matilda API...")

    # Hämta innevarande vecka, måndag till söndag
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    params = {
        "distributorId": DISTRIBUTOR_ID,
        "startDate": monday.isoformat(),
        "endDate": sunday.isoformat(),
        "lang": "sv",
    }

    url = API_URL + "?" + urllib.parse.urlencode(params)

    print(f"API URL: {url}")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")

    print(f"Matilda API svarade med {len(raw)} tecken.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Kunde inte läsa Matildas JSON-data: {e}"
        )

    print("JSON-data kunde läsas.")

    meals = data.get("meals", [])

    print(f"Hittade {len(meals)} måltider.")

    result = []

    for meal in meals:
        date = meal.get("date", "")
        name = meal.get("name") or ""

        dishes = []

        for course in meal.get("courses", []):
            course_name = course.get("name")

            if course_name:
                dishes.append(course_name.strip())

        if date and dishes:
            result.append(
                {
                    "date": date,
                    "name": name,
                    "dishes": dishes,
                }
            )

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": url,
        "meals": result,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Sparade {len(result)} menyposter till {OUTPUT_FILE}")


if __name__ == "__main__":
    fetch_menu()
