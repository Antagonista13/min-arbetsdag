import json
from datetime import datetime
from pathlib import Path

import openpyxl

INPUT_FILE = "Uppdrag.xlsx"
OUTPUT_FILE = "resursteam.json"
SHEET_NAME = "UPPDRAG"


def is_blank(value):
    return value is None or str(value).strip() == ""


def serialize_date(value):
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value).strip()


def is_active(row):
    return row.get("Avslut") is False and any(
        not is_blank(row.get(key))
        for key in ("SKOLA", "ELEV", "UPPDRAGSBESKRIVNING")
    )


def needs_follow_up(row):
    return is_active(row) and (
        is_blank(row.get("ANSVARIG")) or is_blank(row.get("Placering"))
    )


def load_assignments(path=INPUT_FILE):
    workbook = openpyxl.load_workbook(path, data_only=True)

    if SHEET_NAME not in workbook.sheetnames:
        raise ValueError(f"Saknar bladet '{SHEET_NAME}' i {path}")

    sheet = workbook[SHEET_NAME]

    headers = [cell.value for cell in sheet[3]]

    if not headers or "Avslut" not in headers:
        raise ValueError("Kunde inte hitta rubrikerna i rad 3.")

    assignments = []

    for values in sheet.iter_rows(min_row=4, values_only=True):
        row = dict(zip(headers, values))

        if not is_active(row):
            continue

        assignments.append({
            "school": row.get("SKOLA") or "",
            "student": row.get("ELEV") or "",
            "grade": row.get("Årsk."),
            "description": row.get("UPPDRAGSBESKRIVNING") or "",
            "start": serialize_date(row.get("START")),
            "end": serialize_date(row.get("SLUT")),
            "priority": row.get("PRIO"),
            "responsible": row.get("ANSVARIG") or "",
            "placement": row.get("Placering") or "",
            "notes": row.get("ÖVRIGT") or "",
            "needsFollowUp": needs_follow_up(row),
        })

    return assignments


def fetch_resursteam(input_file=INPUT_FILE, output_file=OUTPUT_FILE):
    assignments = load_assignments(input_file)

    result = {
        "updatedAt": datetime.now().astimezone().isoformat(),
        "summary": {
           "activeAssignments": len(assignments),
            "totalAssignments": len(assignments),
            "followUp": sum(
                1 for item in assignments
                if item["needsFollowUp"]
            ),
        },
        "assignments": assignments,
    }

    Path(output_file).write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8",
    )

    print(
        f"Resursteam: "
        f"{result['summary']['activeAssignments']} aktiva uppdrag, "
        f"{result['summary']['followUp']} att följa upp."
    )

    print(f"Skrev {output_file}")


if __name__ == "__main__":
    fetch_resursteam()
