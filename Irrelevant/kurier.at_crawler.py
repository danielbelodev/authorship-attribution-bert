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

    article_body = article.find("section", class_="article-main")
    if article_body is None:
        return ""

    paragraphs = article_body.find_all("div", class_=lambda x: x and x.startswith('paragraph'))

    if not paragraphs:
        return ""

    content = " ".join([para.get_text(strip=True) for para in paragraphs])
    return content

def read_seen_urls(file_path):
    seen_urls = set()
    try:
        with open(file_path, newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header
            for row in reader:
                if row:  # Skip empty rows
                    seen_urls.add(row[0])
    except FileNotFoundError:
        pass
    return seen_urls

def crawl_sitemap(start_year, start_month, start_day, seen_urls, days_to_crawl=1):
    current_date = datetime(start_year, start_month, start_day)
    collected_data = []

    for _ in range(days_to_crawl):
        year, month, day = current_date.year, current_date.month, current_date.day
        base_url = "https://kurier.at/sitemaps/article_{}-{}-{}.xml"
        url = base_url.format(year, f'{month:02}', f'{day:02}')
        print(f"Crawling URL: {url}")

        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching sitemap {url}: {e}")
            current_date += timedelta(days=1)
            continue

        sitemap_content = response.content
        soup = BeautifulSoup(sitemap_content, 'xml')
        url_tags = soup.find_all('url')

        if not url_tags:
            current_date += timedelta(days=1)
            continue

        for url_tag in url_tags:
            loc = url_tag.find('loc').text

            if loc in seen_urls:
                continue

            seen_urls.add(loc)
            lastmod = url_tag.find('lastmod').text
            content = extract_article_content(loc)

            # Only add to collected_data if content is not empty
            if content:
                collected_data.append((loc, lastmod, content))

        current_date += timedelta(days=1)

    return collected_data

# Starte mit einem spezifischen Datum und messe die Zeit für einen Tag
start_year, start_month, start_day = 2013, 1, 1
days_to_crawl = 1

# Gelesene URLs aus der Datei
seen_urls = read_seen_urls("urls.csv")

start_time = time.time()
new_urls = crawl_sitemap(start_year, start_month, start_day, seen_urls, days_to_crawl)
end_time = time.time()

elapsed_time_per_day = end_time - start_time
print(f"Elapsed time for {days_to_crawl} day(s): {elapsed_time_per_day:.2f} seconds")

# Hochrechnung auf einen Monat (30 Tage)
elapsed_time_per_month = elapsed_time_per_day * 30
print(f"Estimated time for one month: {elapsed_time_per_month / 60:.2f} minutes")

# Hochrechnung auf ein Jahr (12 Monate)
elapsed_time_per_year = elapsed_time_per_month * 12
print(f"Estimated time for one year: {elapsed_time_per_year / 60:.2f} minutes")

# Hochrechnung auf mehrere Jahre, z.B. 11 Jahre
years_to_crawl = 11
elapsed_time_total = elapsed_time_per_year * years_to_crawl
print(f"Estimated time for {years_to_crawl} years: {elapsed_time_total / 60:.2f} minutes")

# Speichere die neuen URLs, das Datum und den Inhalt in eine CSV-Datei
with open("urls.csv", "a", newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerows(new_urls)

print(f"Total new URLs collected: {len(new_urls)}")
