import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import os

def extract_article_content(url):
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Fehler beim Abrufen der Seite {url}, Statuscode: {response.status_code}")
        return ""
    
    article = BeautifulSoup(response.text, 'html.parser')
    article_body = article.find("div", {"class": 'article-body'})
    
    if article_body is None:
        print(f"Dieser Artikel hat keinen Body: {url}")
        return ""
    
    paragraphs = article_body.find_all('p')
    
    if not paragraphs:
        print(f"Keine Paragraphen gefunden in: {url}")
        return ""

    content = "\n".join([para.get_text() for para in paragraphs])
    return content

def parse_sitemap(sitemap_url):
    response = requests.get(sitemap_url)
    
    if response.status_code != 200:
        print(f"Fehler beim Abrufen der Sitemap {sitemap_url}, Statuscode: {response.status_code}")
        return []

    sitemap = BeautifulSoup(response.text, 'xml')
    url_entries = sitemap.find_all('url')
    
    data = []
    
    for entry in url_entries:
        loc = entry.find('loc').get_text()
        lastmod = entry.find('lastmod').get_text() if entry.find('lastmod') else 'N/A'
        data.append((loc, lastmod))
    
    return data

def load_existing_urls(filename):
    if not os.path.exists(filename):
        return set()
    
    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Überspringe die Header-Zeile
        existing_urls = {row[0] for row in reader}
    
    return existing_urls

def save_to_csv(data, filename="articles.csv"):
    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        for url, loc, lastmod, content in data:
            writer.writerow([url, loc, lastmod, content])

def process_sitemaps(start_year, start_month, csv_filename):
    existing_urls = load_existing_urls(csv_filename)
    
    current_year = datetime.now().year
    current_month = datetime.now().month

    # Wenn die Datei noch nicht existiert, erstelle sie mit Headern
    if not existing_urls:
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["URL", "Loc", "Lastmod", "Content"])

    for year in range(start_year, current_year + 1):
        for month in range(1, 13):
            if year == start_year and month < start_month:
                continue
            if year == current_year and month > current_month:
                break
            
            sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{year}-{str(month).zfill(2)}.xml"
            print(f"Verarbeite Sitemap: {sitemap_url}")
            articles_data = parse_sitemap(sitemap_url)

            csv_data = []
            for loc, lastmod in articles_data:
                if loc in existing_urls:
                    print(f"Überspringe bereits vorhandene URL: {loc}")
                    continue
                
                print(f"Extrahiere Inhalt von: {loc}")
                content = extract_article_content(loc)
                csv_data.append((loc, loc, lastmod, content))
                
            save_to_csv(csv_data, csv_filename)

# Startjahr und -monat für die Sitemap-Navigation
start_year = 2013
start_month = 1
csv_filename = "articles.csv"

process_sitemaps(start_year, start_month, csv_filename)
