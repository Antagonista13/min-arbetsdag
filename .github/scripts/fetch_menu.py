import json
import re
import urllib.request
from datetime import datetime

MENU_URL = "https://menu.matildaplatform.com/meals/week/68d18b0e30b565aba61bf59e_boras-ganghesterskolan-kok"

OUTPUT_FILE = "menu.json"


def fetch_menu():
    print("Hämtar matsedel från Matilda...")

    request = urllib.request.Request(
        MENU_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")

    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )

    if not match:
        raise RuntimeError("Kunde inte hitta __NEXT_DATA__ på Matilda-sidan.")

    data = json.loads(match.group(1))

    meals = data.get("props", {}).get("pageProps", {}).get("meals", [])

    if not meals:
        raise RuntimeError("Ingen meny hittades i Matilda-datan.")

    result = []

    for meal in meals:
        date = meal.get("date")
        name = meal.get("name")

        if not date:
            continue

        courses = meal.get("courses", [])

        dishes = []

        for course in courses:
            course_name = course.get("name")

            if course_name and course_name.strip():
                dishes.append(course_name.strip())

        if not dishes:
            continue

        result.append(
            {
                "date": date,
                "name": name or "",
                "dishes": dishes,
            }
        )

    output = {
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "source": MENU_URL,
        "meals": result,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Sparade {len(result)} menyposter till {OUTPUT_FILE}")


if __name__ == "__main__":
    fetch_menu()
