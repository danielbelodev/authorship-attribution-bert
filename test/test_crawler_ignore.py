import requests
from bs4 import BeautifulSoup
import csv

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

def crawl_sitemap(url, limit=50):
    collected_data = []

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

    count = 0
    for url_tag in url_tags:
        if count >= limit:
            break

        loc = url_tag.find('loc').text
        lastmod = url_tag.find('lastmod').text
        print(f"Processing Article URL: {loc}")
        content, author = extract_article_content(loc)

        # Only add to collected_data if content is not empty
        if content:
            collected_data.append((loc, lastmod, author, content))
            count += 1

    # Save collected data to CSV after processing this sitemap
    if collected_data:
        save_to_csv("hallo.csv", collected_data)

    return collected_data

# Crawl the sitemap and process only 50 articles
sitemap_url = "https://www.derstandard.at/sitemaps/sitemap-2024-08.xml"
crawl_sitemap(sitemap_url, limit=50)

# Final count of collected data

