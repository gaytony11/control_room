import requests
import os
import time

API_TOKEN = "6eb684ed401640309c4826f4da16b63c"

OUTPUT_DIR = r"C:\Users\44752\Desktop\Control Room\data\vehicles"

SEARCH_QUERY = "skoda"
MAX_MODELS = 50   # change to however many you want

headers = {
    "Authorization": f"Token {API_TOKEN}"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

def search_models(query, max_models):

    url = "https://api.sketchfab.com/v3/search"

    params = {
        "q": query,
        "type": "models",
        "downloadable": "true",
        "count": max_models
    }

    r = requests.get(url, headers=headers, params=params)

    if r.status_code != 200:
        print("Search failed")
        print(r.text)
        return []

    data = r.json()

    return data["results"]


def download_model(uid, name):

    info_url = f"https://api.sketchfab.com/v3/models/{uid}/download"

    r = requests.get(info_url, headers=headers)

    if r.status_code != 200:
        print(f"Skipping {name} (not downloadable)")
        return

    data = r.json()

    glb_url = data["glb"]["url"]

    safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()

    filename = os.path.join(OUTPUT_DIR, f"{safe_name}_{uid}.glb")

    print(f"Downloading: {name}")

    model_data = requests.get(glb_url).content

    with open(filename, "wb") as f:
        f.write(model_data)

    time.sleep(1)


models = search_models(SEARCH_QUERY, MAX_MODELS)

print(f"Found {len(models)} models")

for model in models:

    uid = model["uid"]
    name = model["name"]

    download_model(uid, name)

print("Done.")
