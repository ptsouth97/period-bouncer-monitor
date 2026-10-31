import requests

API_TOKEN = "e341e917a6671dc337ad9993f93afa518c4d8d27"

headers = {
    "Authorization": f"Token {API_TOKEN}"
}

r = requests.get(
    "https://api.aavso.org/v2/api/observations/photometry/",
    headers=headers,
    params={
        "target": "LL And"
    }
)

print(r.status_code)

data = r.json()

print("Count:", data["count"])
