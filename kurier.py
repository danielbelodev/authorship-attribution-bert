import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime, timedelta
import time

#ist ein Bastard
def extract_article_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return "", ""

    article = BeautifulSoup(response.text, 'html.parser')

    # Extracting publication date and time
    date_span = article.find("span", class_="headerComp-author-date")
    if date_span:
        publication_datetime = date_span.get_text(strip=True)
    else:
        publication_datetime = ""

    article_body = article.find("section", class_="article-main")
    if article_body is None:
        print("Dieser Artikel hat keinen Body")
        return "", publication_datetime

    paragraphs = article_body.find_all("div", class_=lambda x: x and x.startswith('paragraph'))

    if not paragraphs:
        print("Keine Paragraphen gefunden")
        return "", publication_datetime

    content = " ".join([para.get_text(strip=True) for para in paragraphs])
    return content, publication_datetime

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
            content, publication_datetime = extract_article_content(loc)
            print(f"Processing URL: {loc}, Publication DateTime: {publication_datetime}")
            urls.append((loc, lastmod, publication_datetime, content))

        # Pause to avoid overloading the server
        time.sleep(1)

        current_date += timedelta(days=1)
    
    return urls

# Starte mit einem spezifischen Datum und einem Enddatum
start_date = datetime(2013, 1, 1)
end_date = datetime(2013, 1, 10)  # Beispielsweise crawlen wir nur die ersten 10 Tage von Januar 2013

all_urls = crawl_sitemap(start_date, end_date)

# Speichere die URLs, das Datum und den Inhalt in eine CSV-Datei
with open("urls_kurier.csv", "w", newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["URL", "Last Modified", "Publication DateTime", "Content"])
    writer.writerows(all_urls)

print(f"Total URLs collected: {len(all_urls)}")
