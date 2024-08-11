import asyncio
import aiohttp
from bs4 import BeautifulSoup
import csv
from datetime import datetime, timedelta
import time

# Semaphore zur Begrenzung der gleichzeitigen Anfragen
semaphore = asyncio.Semaphore(10)

async def extract_article_content(session, url, retries=3):
    for attempt in range(retries):
        try:
            async with semaphore, session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                response.raise_for_status()
                article = BeautifulSoup(await response.text(), 'html.parser')
                
                # Anpassung für derStandard: Suche nach dem 'article-body'-Abschnitt
                article_body = article.find("section", class_="article-body")
                if article_body is None:
                    return ""
                
                paragraphs = article_body.find_all("p")
                return " ".join([para.get_text(strip=True) for para in paragraphs])
        
        except asyncio.TimeoutError:
            if attempt < retries - 1:
                print(f"Timeout error for URL: {url}, retrying... ({attempt+1}/{retries})")
                await asyncio.sleep(2)  # Wartezeit vor dem erneuten Versuch
                continue
            else:
                print(f"Timeout error for URL: {url}, giving up.")
                return ""
        
        except aiohttp.ClientError as e:
            print(f"Request error for URL {url}: {e}")
            return ""

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

async def crawl_sitemap(session, start_year, start_month, seen_urls, months_to_crawl=1):
    current_date = datetime(start_year, start_month, 1)
    collected_data = []

    for _ in range(months_to_crawl):
        year, month = current_date.year, current_date.month
        print(f"Processing year: {year}, month: {month:02}")  # Fortschrittsanzeige

        base_url = "https://www.derstandard.at/sitemaps/sitemap-{}-{}.xml"
        url = base_url.format(year, f'{month:02}')
        print(f"Crawling URL: {url}")

        try:
            async with session.get(url) as response:
                response.raise_for_status()
                sitemap_content = await response.read()
        
        except aiohttp.ClientError as e:
            print(f"Error fetching sitemap {url}: {e}")
            current_date += timedelta(days=30)
            continue

        soup = BeautifulSoup(sitemap_content, 'xml')
        url_tags = soup.find_all('url')

        if not url_tags:
            current_date += timedelta(days=30)
            continue

        tasks = []
        for url_tag in url_tags:
            loc = url_tag.find('loc').text

            if loc in seen_urls:
                continue

            seen_urls.add(loc)
            lastmod = url_tag.find('lastmod').text
            tasks.append(asyncio.create_task(process_article(session, loc, lastmod, collected_data)))

        await asyncio.gather(*tasks)
        current_date += timedelta(days=30)

    return collected_data

async def process_article(session, loc, lastmod, collected_data):
    content = await extract_article_content(session, loc)
    if content:
        collected_data.append((loc, lastmod, content))

async def crawl_articles_from_start_year(start_year, output_file):
    seen_urls = read_seen_urls(output_file)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for month in range(1, 13):  # 12 Monate
            tasks.append(crawl_sitemap(session, start_year, month, seen_urls, 1))
        await asyncio.gather(*tasks)

    return seen_urls

def main():
    start_year = 2013
    output_file = "urls.csv"

    start_time = time.time()

    loop = asyncio.get_event_loop()
    seen_urls = loop.run_until_complete(crawl_articles_from_start_year(start_year, output_file))

    end_time = time.time()

    elapsed_time_per_year = (end_time - start_time) / 60  # Minuten
    print(f"Elapsed time for one year: {elapsed_time_per_year:.2f} minutes")

    years_to_crawl = 11
    elapsed_time_total = elapsed_time_per_year * years_to_crawl
    print(f"Estimated time for {years_to_crawl} years: {elapsed_time_total:.2f} minutes")

    with open(output_file, "a", newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(seen_urls)

    print(f"Total new URLs collected: {len(seen_urls)}")

if __name__ == "__main__":
    main()
