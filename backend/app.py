from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import os
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

# =========================
# OCR.SPACE
# =========================
def extract_text(path):
    url = "https://api.ocr.space/parse/image"

    payload = {
        "apikey": "helloworld",  # gratuit (limité)
        "language": "fre"
    }

    try:
        with open(path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files, data=payload)
            result = response.json()

        return result["ParsedResults"][0]["ParsedText"]

    except Exception as e:
        print("OCR ERROR:", e)
