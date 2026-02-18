import requests
import os
import time

API_TOKEN = "6eb684ed401640309c4826f4da16b63c"

COLLECTION_UID = "00d22c2772c544629f28a2b6250d45a6"

OUTPUT_DIR = r"C:\Users\44752\Desktop\Control Room\data\vehicles\sketchfab_collection"

headers = {
    "Authorization": f"Token {API_TOKEN}"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_collection_models(collection_uid):

    url = f"https://api.sketchfab.com/v3/collections/{collection_uid}/models"

    models = []

    while url:

        r = requests.get(url, headers=headers)

        if r.status_code != 200:
            print("Failed to fetch collection")
            print(r.text)
            return models

        data = r.json()

        models.extend(data["results"])

        url = data["next"]

    return models


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


print("Fetching collection models...")

models = get_collection_models(COLLECTION_UID)

print(f"Found {len(models)} models")

for model in models:

    uid = model["uid"]
    name = model["name"]

    download_model(uid, name)

print("Complete.")
