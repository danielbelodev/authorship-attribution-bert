import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime

# Define the cookie for GDPR compliance
COOKIES = {'DSGVO_ZUSAGE_V1': 'true'}

def extract_article_content(url):
    try:
        response = requests.get(url, cookies=COOKIES)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return "", ""

    article = BeautifulSoup(response.text, 'html.parser')

    # Extract the author
    author = "kein Autor"  # Default value
    header = article.find("header")
    if header:
        author_span = header.find("span", class_="simple")
        if author_span:
            author = author_span.get_text(strip=True)

    # Extract the article body
    article_body = article.find("div", class_="article-body")
    if article_body is None:
        return "", author

    # Collect the text content, skipping paragraphs within <aside> tags
    content = []
    for para in article_body.find_all("p"):
        # Check if the paragraph is inside an <aside> element
        if para.find_parent("aside") is not None:
            continue
        content.append(para.get_text(strip=True))

    return " ".join(content), author

def save_to_csv(file_path, data):
    with open(file_path, "a", newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(data)
    print(f"Saved {len(data)} new URLs to {file_path}")

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

def crawl_sitemap(url):
    collected_data = []
    seen_urls = read_seen_urls("urls.csv")

    print(f"Crawling Sitemap URL: {url}")

    try:
        response = requests.get(url, cookies=COOKIES)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching sitemap {url}: {e}")
        return collected_data

    sitemap_content = response.content
    soup = BeautifulSoup(sitemap_content, 'xml')
    url_tags = soup.find_all('url')

    if not url_tags:
        return collected_data

    for url_tag in url_tags:
        loc = url_tag.find('loc').text
        if loc in seen_urls:
            continue

        lastmod = url_tag.find('lastmod').text
        print(f"Processing Article URL: {loc}")
        content, author = extract_article_content(loc)

        # Only add to collected_data if content is not empty
        if content:
            collected_data.append((loc, lastmod, author, content))
            seen_urls.add(loc)

    # Save collected data to CSV after processing this sitemap
    if collected_data:
        save_to_csv("urls.csv", collected_data)

    return collected_data

# Crawl the sitemap and process all articles
sitemap_url = "https://www.derstandard.at/sitemaps/sitemap-2024-08.xml"
crawl_sitemap(sitemap_url)

# Final count of collected data
print(f"Total new URLs collected: {len(read_seen_urls('urls.csv'))}")
