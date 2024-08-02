import requests  # Holt sich Daten von Websites
from bs4 import BeautifulSoup  # Parst HTML/XML-Daten
import csv  # Zum Schreiben von CSV-Dateien

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
    
    urls = []  # Liste für gesammelte URLs
    for url_tag in soup.find_all('url'):  # Geht alle URL-Tags durch
        loc = url_tag.find('loc').text  # Holt sich die URL
        lastmod = url_tag.find('lastmod').text  # Holt sich das Datum der letzten Änderung
        urls.append((loc, lastmod))  # Fügt URL und Datum der Liste hinzu
    
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
