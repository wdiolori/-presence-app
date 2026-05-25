from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import os
import json
from rapidfuzz import fuzz

app = Flask(__name__)
CORS(app)

# =========================
# CONFIG AIRTABLE
# =========================
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

API_KEY = os.environ.get("AIRTABLE_API_KEY")
BASE_ID = "appxl7Pyofhifm8ka"
TABLE = "tblIxx5StSEVYzpR7"

FIELD_LAST = "Nom"
FIELD_FIRST = "Prénom"
FIELD_STATUS = "Aujourd'hui"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

from openai import OpenAI
import base64

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def extract_names_from_image(path):

    with open(path, "rb") as f:
        image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Voici une feuille de présence. Extrais uniquement les noms et prénoms sous forme de liste JSON."
                    },
                    {
                        "type": "input_image",
                        "image_base64": image_base64
                    }
                ],
            }
        ],
    )

    text = response.output[0].content[0].text

    print("AI RESPONSE:", text)

    try:
        names = json.loads(text)
        return names
    except:
        return []
``

# =========================
# AIRTABLE
# =========================
def get_records():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"
    res = requests.get(url, headers=HEADERS).json()
    return res.get("records", [])


def update_record(record_id, status):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}/{record_id}"
    requests.patch(url, headers=HEADERS,
        json={"fields": {FIELD_STATUS: status}}
    )


def create_record(last, first, status):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"

    requests.post(url, headers=HEADERS, json={
        "fields": {
            FIELD_LAST: last,
            FIELD_FIRST: first,
            FIELD_STATUS: status
        }
    })

# =========================
# MATCHING
# =========================
def find_matches(name, records):
    results = []

    for r in records:
        f = r.get("fields", {})

        db_name = f"{f.get(FIELD_LAST, '')} {f.get(FIELD_FIRST, '')}"

        score = fuzz.token_sort_ratio(name.lower(), db_name.lower())

        if score > 60:
            results.append({
                "id": r["id"],
                "name": db_name,
                "score": score
            })

    return sorted(results, key=lambda x: x["score"], reverse=True)[:3]

# =========================
# ROUTES API
# =========================
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    status = request.form["status"]

    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

print("📸 Image reçue:", file.filename)

names = extract_names_from_image(path)
print("AI NAMES:", names)

records = get_records()

results = []

    for name in names:
        matches = find_matches(name, records)

        results.append({
            "input": name,
            "matches": matches
        })

    return jsonify(results)


@app.route("/validate", methods=["POST"])
def validate():
    data = request.json
    action = data["action"]
    status = data["status"]

    if action == "update":
        update_record(data["record_id"], status)

    elif action == "create":
        parts = data["name"].split()
        last = " ".join(parts[:-1])
        first = parts[-1]

        create_record(last, first, status)

    return jsonify({"ok": True})


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
