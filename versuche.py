import requests

from bs4 import BeautifulSoup
import csv

def extract_article_content(url):
    response = requests.get(url).text
    article = BeautifulSoup(response, 'html.parser')
    
    # Assuming the main content is within a specific tag, e.g., <article> or a class, update this selector accordingly
    article_body = article.find("div", {"class": 'article-body'})
    if article_body is None:
        print("Dieser Artikel hat keinen Body")
    
    paragraphs = article_body.find_all('p')
    content = [para.get_text() for para in paragraphs]
    print(f"Anzahl der gefundenen Paragraphen: {len(paragraphs)}")
    return content

url = input("Geben sie bitte eine URL ein: ")
print(extract_article_content(url))



