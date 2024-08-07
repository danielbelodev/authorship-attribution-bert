import csv
from datetime import datetime, timedelta
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Funktion zur Extraktion des Artikelinhalts von einer gegebenen URL mit Selenium
def extract_article_content(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service('C:/Users/themi/Documents/chromedriver-win64/chromedriver.exe')

    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.article-body')))

        article_content = driver.find_element(By.CSS_SELECTOR, 'div.article-body')

        if not article_content:
            paragraphs = driver.find_elements(By.TAG_NAME, 'p')
            if not paragraphs:
                return ""
            content = " ".join([para.text.strip() for para in paragraphs])
        else:
            paragraphs = article_content.find_elements(By.TAG_NAME, 'p')
            if not paragraphs:
                return ""
            content = " ".join([para.text.strip() for para in paragraphs])
        
        return content

    except Exception as e:
        print(f"Error extracting content from {url}: {e}")
        return ""

    finally:
        driver.quit()

def read_seen_urls(file_path):
    seen_urls = set()
    try:
        with open(file_path, newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)
            for row in reader:
                if row:
                    seen_urls.add(row[0])
    except FileNotFoundError:
        pass
    return seen_urls

def crawl_sitemap(start_year, start_month, seen_urls):
    current_date = datetime(start_year, start_month, 1)
    today = datetime.today()
    collected_data = []

    while current_date < today:
        year, month = current_date.year, current_date.month
        base_url = "https://www.derstandard.at/sitemaps/sitemap-{}-{}.xml"
        url = base_url.format(year, f'{month:02}')
        print(f"Crawling URL: {url}")

        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching sitemap {url}: {e}")
            current_date += timedelta(days=30)
            continue

        sitemap_content = response.content
        soup = BeautifulSoup(sitemap_content, 'xml')
        url_tags = soup.find_all('url')

        if not url_tags:
            current_date += timedelta(days=30)
            continue

        for url_tag in url_tags:
            loc = url_tag.find('loc').text

            if loc in seen_urls:
                continue

            seen_urls.add(loc)
            lastmod = url_tag.find('lastmod').text
            content = extract_article_content(loc)

            if content:
                collected_data.append((loc, lastmod, content))

        if month == 12:
            current_date = datetime(year + 1, 1, 1)
        else:
            current_date = datetime(year, month + 1, 1)

    return collected_data

start_year, start_month = 2024, 1
seen_urls = read_seen_urls("urls.csv")

start_time = time.time()
new_urls = crawl_sitemap(start_year, start_month, seen_urls)
end_time = time.time()

elapsed_time = end_time - start_time
print(f"Elapsed time: {elapsed_time:.2f} seconds")

with open("urls.csv", "a", newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerows(new_urls)

print(f"Total new URLs collected: {len(new_urls)}")
