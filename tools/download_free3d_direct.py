import requests
import os

DOWNLOAD_URL = "https://free3d.com/dl-files.php?p=51a5a52f46e0dab68d3b5a3b&f=0"

OUTPUT_DIR = r"C:\Users\44752\Desktop\Control Room\assets\free3d_vehicles"

# YOUR SESSION COOKIE
SESSION_COOKIE = "PHPSESSID=fkkq8u23dsk8udcg8qjcjtrnlt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://free3d.com/",
    "Cookie": SESSION_COOKIE
}

def download():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Connecting...")

    r = requests.get(
        DOWNLOAD_URL,
        headers=HEADERS,
        stream=True
    )

    print("Status:", r.status_code)

    if r.status_code != 200:
        print("Failed.")
        return

    filename = "model.zip"

    if "Content-Disposition" in r.headers:
        cd = r.headers["Content-Disposition"]
        if "filename=" in cd:
            filename = cd.split("filename=")[1].strip('"')

    path = os.path.join(OUTPUT_DIR, filename)

    print("Saving:", filename)

    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    print("DONE")


download()
