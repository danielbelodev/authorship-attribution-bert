import requests
from bs4 import BeautifulSoup

def extract_article_content(url):
    response = requests.get(url)
    
    # Überprüfung, ob der Request erfolgreich war
    if response.status_code != 200:
        print(f"Fehler beim Abrufen der Seite, Statuscode: {response.status_code}")
        return []

    article = BeautifulSoup(response.text, 'html.parser')

    # Debugging: Struktur der HTML-Daten anzeigen
    print(f"HTML-Struktur:\n{article.prettify()}")  # Begrenzen auf die ersten 1000 Zeichen für Übersichtlichkeit

    # Assuming the main content is within a specific tag, e.g., <article> or a class, update this selector accordingly
    article_body = article.find("div", {"class": 'article-body'})
    
    if article_body is None:
        print("Dieser Artikel hat keinen Body")
        return []
    
    # Debugging: Anzeigen der Struktur des gefundenen Artikels
    print(f"Gefundener Artikel-Body:\n{article_body.prettify()}")  # Begrenzen auf die ersten 1000 Zeichen

    paragraphs = article_body.find_all('p')
    
    if not paragraphs:
        print("Keine Paragraphen gefunden")
        return []

    content = [para.get_text() for para in paragraphs]

    # Debugging: Anzahl der gefundenen Paragraphen
    print(f"Anzahl der gefundenen Paragraphen: {len(paragraphs)}")

    return content

url = input("Geben Sie bitte eine URL ein: ")
article_content = extract_article_content(url)
for i, paragraph in enumerate(article_content):
    print(f"Paragraph {i+1}: {paragraph}")
