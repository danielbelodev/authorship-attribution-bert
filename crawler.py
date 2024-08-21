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

    article_body = article.find("div", class_="article-body")
    if article_body is None:
        return ""

    paragraphs = article_body.find_all("p")

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

def save_to_csv(file_path, data):
    with open(file_path, "a", newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(data)
    print(f"Saved {len(data)} new URLs to {file_path}")

def crawl_sitemap(url, seen_urls):
    collected_data = []

    print(f"Crawling Sitemap URL: {url}")

    try:
        response = requests.get(url)
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

        seen_urls.add(loc)
        lastmod = url_tag.find('lastmod').text
        print(f"Processing Article URL: {loc}")
        content = extract_article_content(loc)

        # Only add to collected_data if content is not empty
        if content:
            collected_data.append((loc, lastmod, content))

    # Save collected data to CSV after processing this sitemap
    if collected_data:
        save_to_csv("urls.csv", collected_data)

    return collected_data

def crawl_all_sitemaps(start_date, end_date):
    current_date = start_date
    seen_urls = read_seen_urls("urls.csv")

    start_time = time.time()

    while current_date <= end_date:
        year, month = current_date.year, current_date.month

        # Monthly Sitemap
        monthly_sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{year}-{month:02}.xml"
        crawl_sitemap(monthly_sitemap_url, seen_urls)

        # Daily Sitemaps for the current month
        num_days = (current_date.replace(day=28) + timedelta(days=4)).day  # Get the number of days in the month
        for day in range(1, num_days + 1):
            daily_sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{year}-{month:02}-{day:02}.xml"
            crawl_sitemap(daily_sitemap_url, seen_urls)

        # Move to the next month
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Elapsed time for crawling: {elapsed_time / 60:.2f} minutes")

# Start crawling from January 2013 until today
start_date = datetime(2024, 5, 1)
end_date = datetime.now()

crawl_all_sitemaps(start_date, end_date)

# Final count of collected data
print(f"Total new URLs collected: {len(read_seen_urls('urls.csv'))}")