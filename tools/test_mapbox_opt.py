from pathlib import Path
from dotenv import load_dotenv
import os, requests

# charge le .env à la racine du projet
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

token = os.getenv("MAPBOX_TOKEN")
print("Token prefix:", None if not token else token[:3])  # doit afficher 'pk.'

# petit appel "matrix" simple pour valider l'accès
url = (
    "https://api.mapbox.com/directions-matrix/v1/mapbox/driving/"
    "-0.37,43.30;-0.36,43.31"
    "?annotations=duration,distance"
    f"&access_token={token}"
)
r = requests.get(url, timeout=20)
print("HTTP:", r.status_code)
print(r.text[:400])
