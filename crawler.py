import requests  # Holt sich Daten von Websites
from bs4 import BeautifulSoup  # Parst HTML/XML-Daten
import csv  # Zum Schreiben von CSV-Dateien

#das Problem hier ist, dass ich nur einen Paragraphen bekomme
def extract_article_content(url):
    response = requests.get(url).text
    article = BeautifulSoup(response, 'html.parser')
    
    article_body = article.find("div", {"class": 'article-body'})
    if article_body is None:
        print("Dieser Artikel hat keinen Body")
    
    paragraphs = article_body.find_all('p')
    content = [para.get_text() for para in paragraphs]
    print(f"Anzahl der gefundenen Paragraphen: {len(paragraphs)}")
    return content

def crawl_sitemap(year, month):
    base_url = "https://www.derstandard.at/sitemaps/sitemap-{}-{:02d}.xml"  # URL-Format der Sitemap
    url = base_url.format(year, month)  # Ersetze Jahr und Monat
    print(f"Crawling URL: {url}")  # Zeigt die aktuelle URL an
    
    response = requests.get(url)  # Holt sich die Sitemap
    if response.status_code != 200:  # Prüft, ob die Anfrage erfolgreich war
        print(f"Failed to retrieve sitemap for {year}-{month:02d}")  # Gibt Fehler aus, wenn nicht
        return []  # Beendet die Funktion mit leerer Liste

    sitemap_content = response.content  # Holt den Inhalt der Sitemap
    soup = BeautifulSoup(sitemap_content, 'xml')  # Parst den XML-Inhalt
    
    urls = []
    for url_tag in soup.find_all('url'):
        loc = url_tag.find('loc').text
        lastmod = url_tag.find('lastmod').text
        inhalt = extract_article_content(loc) # 

        #hier muss ich ja den link einneschauen, damit ich den content lesen kann

        urls.append((loc, lastmod))
    
    # Gehe zum nächsten Monat
    month += 1
    if month > 12:  # Falls Monat größer als 12 ist
        month = 1  # Setze Monat auf Januar
        year += 1  # Und erhöhe das Jahr

    # Rekursiver Aufruf für den nächsten Monat
    return urls + crawl_sitemap(year, month)

# Starte mit Januar 2023 und hole alle URLs
all_urls = crawl_sitemap(2023, 1)

# Speichere die URLs und das Datum in eine CSV-Datei
with open("urls.csv", "w", newline='', encoding='utf-8') as file:
    writer = csv.writer(file)  # CSV-Schreiber erstellen
    writer.writerow(["URL", "Last Modified"])  # Schreibe die Header-Zeile
    writer.writerows(all_urls)  # Schreibe alle URLs und Daten

print(f"Total URLs collected: {len(all_urls)}")  # Zeige die Gesamtanzahl der gesammelten URLs
