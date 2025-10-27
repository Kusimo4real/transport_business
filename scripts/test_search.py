from fastapi.testclient import TestClient
import json
import sys
import os

# Ensure project root is on sys.path so `import main` works when running from scripts/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import the app from main.py
try:
    import main
except Exception as e:
    print(f"Failed to import main.py: {e}")
    sys.exit(2)

client = TestClient(main.app)

payload = {"origen": "Clinica 27 (IMSS)", "destino": "Jardines de la Mesa"}
print("Request payload:", payload)
resp = client.post("/search", json=payload)
print("Status code:", resp.status_code)
try:
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print("Failed to decode JSON response:", e)
    print("Raw response text:\n", resp.text)
