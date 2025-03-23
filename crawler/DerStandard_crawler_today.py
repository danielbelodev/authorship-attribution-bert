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

    # Check in <header> for the author
    header = article.find("header")
    if header:
        author_span = header.find("span", class_="simple")
        if author_span:
            author = author_span.get_text(strip=True)
    
    # Check in <div class="article-origins"> for the author
    origins_div = article.find("div", class_="article-origins")
    if origins_div:
        author = origins_div.get_text(strip=True)

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
    # Create the file with header if it doesn't exist
    if not os.path.exists(file_path):
        with open(file_path, "w", newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["url", "lastmod", "author", "content"])
    
    # Append the new data
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
        pass  # File will be created when saving
    return seen_urls

def crawl_today_articles():
    """Crawl only today's articles from derstandard.at"""
    # Get today's date
    today = datetime.now()
    today_date = today.date()
    
    # Create the sitemap URL for the current month
    sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{today.year}-{today.month:02}.xml"
    
    print(f"Starting crawler for articles from {today_date}")
    print(f"Using sitemap: {sitemap_url}")
    
    # Initialize data collection
    collected_data = []
    seen_urls = read_seen_urls("urls_today.csv")
    
    try:
        response = requests.get(sitemap_url, cookies=COOKIES)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching sitemap {sitemap_url}: {e}")
        return []

    sitemap_content = response.content
    soup = BeautifulSoup(sitemap_content, 'xml')
    url_tags = soup.find_all('url')

    if not url_tags:
        print("No URLs found in sitemap")
        return []

    print(f"Found {len(url_tags)} URLs in sitemap, filtering for today's articles...")

    for url_tag in url_tags:
        loc = url_tag.find('loc').text
        if loc in seen_urls:
            continue

        lastmod_tag = url_tag.find('lastmod')
        if not lastmod_tag:
            continue
            
        lastmod = lastmod_tag.text
        
        # Parse the lastmod date to check if it's from today
        try:
            lastmod_date = datetime.fromisoformat(lastmod.replace('Z', '+00:00')).date()
            # Skip if not from today
            if lastmod_date != today_date:
                continue
        except (ValueError, TypeError):
            continue

        print(f"Processing article from today: {loc}")
        content, author = extract_article_content(loc)

        # Only add to collected_data if content is not empty
        if content:
            collected_data.append((loc, lastmod, author, content))
            seen_urls.add(loc)

    # Save collected data to CSV
    if collected_data:
        save_to_csv("urls_today.csv", collected_data)
        print(f"Successfully collected {len(collected_data)} articles from today")
    else:
        print("No new articles found for today")

    return collected_data

if __name__ == "__main__":
    import os
    
    # Print start time
    start_time = datetime.now()
    print(f"Crawler started at: {start_time}")
    
    # Run the crawler
    articles = crawl_today_articles()
    
    # Print summary
    end_time = datetime.now()
    duration = end_time - start_time
    print("\nCrawler Summary:")
    print("-" * 50)
    print(f"Date: {datetime.now().date()}")
    print(f"Articles collected: {len(articles)}")
    print(f"Duration: {duration}")
    print(f"Output file: {os.path.abspath('urls_today.csv')}")
    print("-" * 50) 