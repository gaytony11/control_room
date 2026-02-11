import requests

API_URL = "https://commons.wikimedia.org/w/api.php"

def search_commons_images(query, limit=10):
    # 1) Search for file pages in Commons
    params_search = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query + " incategory:File",  # search files
        "srnamespace": 6,  # File namespace
        "srlimit": limit
    }
    r = requests.get(API_URL, params=params_search)
    results = r.json().get("query", {}).get("search", [])

    for item in results:
        title = item["title"]  # e.g., "File:Example.jpg"
        
        # 2) Get imageinfo for that file
        params_info = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size"
        }
        r2 = requests.get(API_URL, params=params_info)
        pages = r2.json().get("query", {}).get("pages", {})

        for page_id, page in pages.items():
            if "imageinfo" in page:
                info = page["imageinfo"][0]
                print(f"Title: {title}")
                print(f"URL:   {info.get('url')}")
                print()

# Example search
search_commons_images("cat", limit=5)
