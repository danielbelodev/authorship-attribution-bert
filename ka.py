import requests

def get_html_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.content  # Use .text for a decoded string
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

# Beispiel-URL
url = "https://www.derstandard.at/story/2000143061568/nato-experte-koschut-erdogans-spiel-ist-durchschaubar"

# HTML-Inhalt abrufen
html_content = get_html_content(url)

if html_content:
    # HTML-Inhalt in einer Datei speichern
    with open("article.html", "wb") as file:  # Use "w" and .text for a decoded string
        file.write(html_content)

    print(f"HTML content saved to article.html")
else:
    print("Failed to retrieve HTML content.")
