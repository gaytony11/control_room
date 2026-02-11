headers = {
    "User-Agent": "MyWikiSearcher/1.0 (your-email@example.com)"
}
r = requests.get(API_URL, params=params_search, headers=headers)

import requests

API_URL = "https://commons.wikimedia.org/w/api.php"

def search_commons_images(query, limit=10):
    """
    Search Wikimedia Commons for media files matching the query,
    and print out direct image URLs.
    """
    params_search = {
        "action": "query",
        "list": "search",
        "srsearch": query + " incategory:File",
        "srnamespace": 6,
        "srlimit": limit,
        "format": "json"
    }

    r = requests.get(API_URL, params=params_search)
    data = r.json()

    items = data.get("query", {}).get("search", [])
    if not items:
        print(f"No results found for: {query}\n")
        return

    print(f"\n=== Results for '{query}' ===\n")

    for item in items:
        title = item["title"]

        # Get detailed image info
        params_info = {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "format": "json"
        }

        r2 = requests.get(API_URL, params=params_info)
        pages = r2.json().get("query", {}).get("pages", {})

        for _, page in pages.items():
            if "imageinfo" in page:
                info = page["imageinfo"][0]
                print(f"Title: {title}")
                print(f"URL:   {info.get('url')}\n")

def main():
    print("📌 Wikimedia Commons Search CLI")
    print("Type a search term (e.g., London Underground, cat, vintage car, etc.)\n")

    while True:
        query = input("Enter search query (or 'exit' to quit): ").strip()
        if query.lower() == "exit":
            print("\nExiting.")
            break
        if not query:
            print("Please enter something to search for.")
            continue

        search_commons_images(query, limit=10)

if __name__ == "__main__":
    main()
