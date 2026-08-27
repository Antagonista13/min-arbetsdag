import json
import re
import urllib.request
from datetime import datetime

MENU_URL = "https://menu.matildaplatform.com/meals/week/68d18b0e30b565aba61bf59e_boras-ganghesterskolan-kok"

OUTPUT_FILE = "menu.json"


def fetch_menu():
    print("Hämtar matsedel från Matilda...")
    print(f"URL: {MENU_URL}")

    request = urllib.request.Request(
        MENU_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")

    print(f"Matilda svarade med {len(html)} tecken.")

    # Spara HTML lokalt så att vi kan undersöka exakt vad Matilda skickar.
    with open("matilda_debug.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Matilda-sidan sparad som matilda_debug.html")

    # Försök hitta Next.js-data
    patterns = [
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    ]

    match = None

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)

        if match:
            print("Hittade __NEXT_DATA__.")
            break

    if not match:
        print("Hittade INTE __NEXT_DATA__.")
        print("Matilda använder sannolikt en annan datastruktur.")
        
        # Försök ändå hitta tydliga måltidsord i HTML-koden.
        keywords = [
            "måndag",
            "tisdag",
            "onsdag",
            "torsdag",
            "fredag",
            "lunch",
            "måltid",
        ]

        found = []

        lower_html = html.lower()

        for keyword in keywords:
            if keyword in lower_html:
                found.append(keyword)

        print(f"Hittade följande nyckelord: {found}")

        # Skapa en tom men giltig menu.json så workflowen inte kraschar.
        output = {
            "updatedAt": datetime.utcnow().isoformat() + "Z",
            "source": MENU_URL,
            "meals": [],
            "status": "Matilda-data kunde inte tolkas automatiskt ännu."
        }

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Kunde inte läsa Matildas JSON-data: {e}"
        )

    print("JSON-data kunde läsas.")

    # Försök hitta meals på flera vanliga nivåer.
    meals = []

    possible_paths = [
        data.get("props", {}).get("pageProps", {}).get("meals"),
        data.get("props", {}).get("pageProps", {}).get("data", {}).get("meals"),
        data.get("props", {}).get("pageProps", {}).get("menu", {}).get("meals"),
    ]

    for candidate in possible_paths:
        if isinstance(candidate, list) and candidate:
            meals = candidate
            break

    if not meals:
        print("Ingen meals-lista hittades i __NEXT_DATA__.")

        output = {
            "updatedAt": datetime.utcnow().isoformat() + "Z",
            "source": MENU_URL,
            "meals": [],
            "status": "Matilda-sidan hittades men matsedelsdatan ligger på en annan nivå."
        }

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return

    result = []

    for meal in meals:
        date = meal.get("date")
        name = meal.get("name", "")

        dishes = []

        for course in meal.get("courses", []):
            course_name = course.get("name")

            if course_name:
                dishes.append(course_name.strip())

        if date and dishes:
            result.append({
                "date": date,
                "name": name,
                "dishes": dishes
            })

    output = {
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "source": MENU_URL,
        "meals": result
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Sparade {len(result)} menyposter till {OUTPUT_FILE}")


if __name__ == "__main__":
    fetch_menu()
