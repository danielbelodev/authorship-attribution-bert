import aiohttp
import asyncio
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Define the cookie that needs to be set for GDPR compliance
COOKIES = {'DSGVO_ZUSAGE_V1': 'true'}

# Function to extract the article content asynchronously
async def extract_article_content(session, url):
    async with session.get(url, cookies=COOKIES) as response:
        if response.status == 200:
            soup = BeautifulSoup(await response.text(), 'html.parser')
            article_body = soup.find('div', class_='article-body')
            if article_body:
                paragraphs = [p.get_text() for p in article_body.find_all('p')]
                content = "\n".join(paragraphs)
                return content
    return None

# Function to parse the sitemap and extract article URLs and dates
async def parse_sitemap(session, sitemap_url):
    async with session.get(sitemap_url, cookies=COOKIES) as response:
        if response.status == 200:
            soup = BeautifulSoup(await response.text(), 'xml')
            urls_dates = [(loc.get_text(), lastmod.get_text())
                          for loc, lastmod in zip(soup.find_all('loc'), soup.find_all('lastmod'))]
            return urls_dates
    return []

# Function to check if a URL is already in the CSV file
def is_url_in_csv(url, csv_file):
    if not os.path.exists(csv_file):
        return False
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            if row and row[0] == url:
                return True
    return False

# Function to crawl articles from a sitemap
async def crawl_articles(session, sitemap_url, output_file):
    urls_dates = await parse_sitemap(session, sitemap_url)
    to_write = []
    
    for url, lastmod in urls_dates:
        if not is_url_in_csv(url, output_file):  # Skip if URL is already in CSV
            print(f"Crawling: {url}")
            content = await extract_article_content(session, url)
            if content:
                to_write.append([url, lastmod, content])
    
    if to_write:
        with open(output_file, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(to_write)  # Write all collected rows at once

# Function to loop through years and months up to the current date
async def crawl_articles_from_start_year(start_year, output_file):
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for year in range(start_year, current_year + 1):
            for month in range(1, 13):
                if year == current_year and month > current_month:
                    break  # Stop if we reach the current month
                sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{year}-{month:02d}.xml"
                print(f"Processing sitemap: {sitemap_url}")
                tasks.append(crawl_articles(session, sitemap_url, output_file))
        
        await asyncio.gather(*tasks)

# Entry point to run the crawler
def main():
    output_file = "articles_2013_to_present.csv"
    start_year = 2013

    # Start the event loop for async crawling
    loop = asyncio.get_event_loop()
    loop.run_until_complete(crawl_articles_from_start_year(start_year, output_file))

# Execute the main function
if __name__ == "__main__":
    main()
