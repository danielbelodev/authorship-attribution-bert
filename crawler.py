import requests
from bs4 import BeautifulSoup
import csv

def crawl_sitemap(year, month):
    base_url = "https://www.derstandard.at/sitemaps/sitemap-{}-{:02d}.xml"
    url = base_url.format(year, month)
    print(f"Crawling URL: {url}")
    
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve sitemap for {year}-{month:02d}")
        return []
    
    sitemap_content = response.content
    soup = BeautifulSoup(sitemap_content, 'xml')
    
    urls = []
    for url_tag in soup.find_all('url'):
        loc = url_tag.find('loc').text
        lastmod = url_tag.find('lastmod').text
        urls.append((loc, lastmod))
    
    # Move to the next month
    month += 1
    if month > 12:
        month = 1
        year += 1

    # Recursively call the function for the next month
    return urls + crawl_sitemap(year, month)

# Start crawling from January 2023 and store all URLs
all_urls = crawl_sitemap(2013, 1)

# Save the URLs and lastmod to a CSV file
def save_urls_to_csv(file_path):
    all_urls = crawl_sitemap(2023, 1)
    with open(file_path, "w", newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["URL", "Last Modified"])
        writer.writerows(all_urls)

if __name__ == "__main__":
    save_urls_to_csv("/path/to/your/airflow/dags/urls.csv")
