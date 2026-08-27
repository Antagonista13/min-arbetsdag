import json
import re
import urllib.request
from datetime import datetime, timezone

MENU_URL = "https://menu.matildaplatform.com/meals/week/68d18b0e30b565aba61bf59e_boras-ganghesterskolan-kok"
OUTPUT_FILE = "menu.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml",
}


def fetch_html(url):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def extract_next_data(html):
    match = re.search(
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )

    if not match:
        raise RuntimeError("Kunde inte hitta __NEXT_DATA__ på Matilda-sidan.")

    return json.loads(match.group(1))


def find_meals(obj):
    """
    Letar rekursivt efter en lista som heter 'meals'.
    Detta gör scriptet mindre känsligt för förändringar
    i Matildas datastruktur.
    """

    if isinstance(obj, dict):

        meals = obj.get("meals")

        if isinstance(meals, list) and meals:
            return meals

        for value in obj.values():
            result = find_meals(value)

            if result:
                return result

    elif isinstance(obj, list):

        for item in obj:
            result = find_meals(item)

            if result:
                return result

    return None


def find_next_url(obj):
    """
    Letar efter Matildas nextURL.
    """

    if isinstance(obj, dict):

        next_url = obj.get("nextURL")

        if isinstance(next_url, str) and next_url:
            return next_url

        for value in obj.values():
            result = find_next_url(value)

            if result:
                return result

    elif isinstance(obj, list):

        for item in obj:
            result = find_next_url(item)

            if result:
                return result

    return None


def parse_date(value):
    if not value:
        return None

    try:
        # Exempel:
        # 2026-08-27T00:00:00
        # 2026-08-27T00:00:00Z
        # 2026-08-27T00:00:00.000Z

        value = value.replace("Z", "+00:00")

        dt = datetime.fromisoformat(value)

        return dt.date().isoformat()

    except Exception:
        return None


def fetch_week(url):
    print(f"Hämtar matsedel: {url}")

    html = fetch_html(url)
    data = extract_next_data(html)

    meals = find_meals(data)

    if not meals:
        raise RuntimeError(
            "Matilda-sidan hittades men ingen måltidslista kunde hittas."
        )

    print(f"Hittade {len(meals)} måltidsposter.")

    return data, meals


def fetch_menu():

    print("Hämtar matsedel från Matilda...")

    # Första veckan
    data, meals = fetch_week(MENU_URL)

    # Matilda skickar normalt en länk till nästa vecka.
    # Vi försöker hämta även den så dashboarden har mer framförhållning.
    next_url = find_next_url(data)

    if next_url:

        if next_url.startswith("/"):
            next_url = "https://menu.matildaplatform.com" + next_url

        print(f"Hittade nästa vecka: {next_url}")

        try:
            _, next_meals = fetch_week(next_url)
            meals = meals + next_meals
        except Exception as error:
            print(f"Varning: kunde inte hämta nästa vecka: {error}")

    result = []

    for meal in meals:

        if not isinstance(meal, dict):
            continue

        date = parse_date(meal.get("date"))

        if not date:
            continue

        name = meal.get("name") or ""

        dishes = []

        courses = meal.get("courses", [])

        if isinstance(courses, list):

            for course in courses:

                if not isinstance(course, dict):
                    continue

                course_name = course.get("name")

                if course_name and course_name.strip():
                    dishes.append(course_name.strip())

        # Om courses saknas försöker vi ändå använda meal-namnet.
        if not dishes and name:
            dishes.append(name.strip())

        if not dishes:
            continue

        result.append(
            {
                "date": date,
                "name": name,
                "dishes": dishes,
            }
        )

    # Sortera efter datum
    result.sort(key=lambda x: x["date"])

    if not result:
        raise RuntimeError(
            "Matilda-data hittades men inga användbara maträtter kunde läsas."
        )

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": MENU_URL,
        "meals": result,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"Sparade {len(result)} menyposter till {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    fetch_menu()
