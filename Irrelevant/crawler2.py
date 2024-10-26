import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime, timedelta
import time

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
    return content

def crawl_sitemap(start_date, end_date):
    base_url = "https://kurier.at/sitemaps/article_{}-{:02d}-{:02d}.xml"
    current_date = start_date
    urls = []

    while current_date <= end_date:
        url = base_url.format(current_date.year, current_date.month, current_date.day)
        print(f"Crawling URL: {url}")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Failed to retrieve sitemap for {current_date.strftime('%Y-%m-%d')}: {e}")
            current_date += timedelta(days=1)
            continue

        sitemap_content = response.content
        soup = BeautifulSoup(sitemap_content, 'xml')
        
        for url_tag in soup.find_all('url'):
            loc = url_tag.find('loc').text
            lastmod = url_tag.find('lastmod').text
            print(f"Processing URL: {loc}")
            inhalt = extract_article_content(loc)
            urls.append((loc, lastmod, inhalt))
        
        # Pause to avoid overloading the server
        time.sleep(1)

        current_date += timedelta(days=1)

    return urls

# Starte mit einem spezifischen Datum
start_date = datetime(2013, 1, 1)
end_date = datetime(2013, 1, 31)  # Example end date

all_urls = crawl_sitemap(start_date, end_date)

# Speichere die URLs, das Datum und den Inhalt in eine CSV-Datei
with open("urls.csv", "w", newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["URL", "Last Modified", "Content"])
    writer.writerows(all_urls)

print(f"Total URLs collected: {len(all_urls)}")
