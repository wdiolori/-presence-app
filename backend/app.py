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

    # FIX 1 : utilisation correcte de l'API OpenAI (chat.completions + image_url)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Voici une feuille de présence. "
                            "Extrais uniquement les noms et prénoms sous forme de liste JSON. "
                            "Réponds UNIQUEMENT avec le JSON brut, sans texte autour, "
                            "sans balises markdown. Exemple : [\"Jean Dupont\", \"Marie Martin\"]"
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=1000
    )

    text = response.choices[0].message.content
    print("AI RESPONSE:", text)

    # FIX 2 : nettoyage des balises markdown éventuelles avant parsing JSON
    try:
        clean = re.sub(r"```json|```", "", text).strip()
        names = json.loads(clean)
        return names if isinstance(names, list) else []
    except Exception as e:
        print("Erreur parsing JSON:", e)
        return []


# =========================
# AIRTABLE
# =========================
def get_records():
    # FIX 3 : gestion de la pagination Airtable (max 100 records par page)
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"
    records = []
    params = {}
    while True:
        res = requests.get(url, headers=HEADERS, params=params).json()
        records.extend(res.get("records", []))
        offset = res.get("offset")
        if not offset:
            break
        params["offset"] = offset
    return records


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
    """
    Teste les deux ordres possibles (Prénom Nom et Nom Prénom) contre
    chaque entrée Airtable et retient le meilleur score.
    """
    parts = name.strip().split()
    # Si au moins 2 mots, on génère les deux variantes ; sinon on garde tel quel
    if len(parts) >= 2:
        variant_a = name                              # tel que reçu
        variant_b = " ".join(parts[1:] + [parts[0]]) # rotation : dernier → premier
        candidates = [variant_a, variant_b]
    else:
        candidates = [name]

    results = []
    for r in records:
        f = r.get("fields", {})
        db_name = f"{f.get(FIELD_LAST, '')} {f.get(FIELD_FIRST, '')}".strip()

        # Score maximum sur les deux variantes
        best_score = max(
            fuzz.token_sort_ratio(c.lower(), db_name.lower())
            for c in candidates
        )

        if best_score > 60:
            results.append({
                "id": r["id"],
                "name": db_name,
                "score": best_score
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
        # On ne peut pas deviner l'ordre, on stocke le premier mot comme Prénom
        # et le reste comme Nom — le front devrait idéalement envoyer les deux champs séparés
        parts = data["name"].strip().split()
        first = parts[0]
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
        create_record(last, first, status)

    return jsonify({"ok": True})


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
