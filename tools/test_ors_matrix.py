# tools/test_ors_matrix.py
import os, requests
from dotenv import load_dotenv

# Charge le fichier .env à la racine du projet
load_dotenv()

api_key = os.getenv("ORS_API_KEY")
if not api_key:
    raise SystemExit("ORS_API_KEY manquant dans .env")

# Rappel: ORS attend [longitude, latitude]
payload = {"locations": [[-0.37, 43.30], [-0.36, 43.31]]}

r = requests.post(
    "https://api.openrouteservice.org/v2/matrix/driving-car",
    headers={"Authorization": api_key, "Content-Type": "application/json"},
    json=payload,
    timeout=20,
)

print("HTTP:", r.status_code)
print(r.text)
