import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime, timedelta

def extract_article_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return ""

    article = BeautifulSoup(response.text, 'html.parser')

    # Ausgabe des HTML-Codes zur Überprüfung der Struktur (optional)
    # print(article.prettify())

    # Suche nach dem `section`-Tag für den Hauptinhalt
    article_body = article.find("section", class_="article-main")
    if article_body is None:
        print("Dieser Artikel hat keinen Body")
        return ""

    # Suche nach allen `div`-Tags, deren Klassenbezeichnung mit "paragraph" beginnt
    paragraphs = article_body.find_all("div", class_=lambda x: x and x.startswith('paragraph'))

    if not paragraphs:
        print("Keine Paragraphen gefunden")
        return ""

    # Extrahiere den Text aus den gefundenen Paragraphen
    content = " ".join([para.get_text(strip=True) for para in paragraphs])
    #print(f"Anzahl der gefundenen Paragraphen: {len(paragraphs)}")
    #print(f"Extrahierter Text: {content[:500]}...")  # Gibt die ersten 500 Zeichen des Inhalts aus
    return content

def crawl_sitemap(year, month, day):
    base_url = "https://kurier.at/sitemaps/article_{}-{:02d}-{:02d}.xml"
    url = base_url.format(year, month, day)
    print(f"Crawling URL: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to retrieve sitemap for {year}-{month:02d}-{day:02d}: {e}")
        return []

    sitemap_content = response.content
    soup = BeautifulSoup(sitemap_content, 'xml')
    
    urls = []
    for url_tag in soup.find_all('url'):
        loc = url_tag.find('loc').text
        lastmod = url_tag.find('lastmod').text
        print(f"Processing URL: {loc}")
        inhalt = extract_article_content(loc)

        urls.append((loc, lastmod, inhalt))
    
    # Gehe zum nächsten Tag
    day += 1
    if day > 31:
        day = 1
        month += 1
        if month > 12:
            month = 1
            year += 1

    return urls + crawl_sitemap(year, month, day)

# Starte mit einem spezifischen Datum
all_urls = crawl_sitemap(2013, 1, 1)

# Speichere die URLs, das Datum und den Inhalt in eine CSV-Datei
with open("urls.csv", "w", newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["URL", "Last Modified", "Content"])
    writer.writerows(all_urls)

print(f"Total URLs collected: {len(all_urls)}")
