from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
import time
"""
da ein robots.txt auf der Seite der "DerStandard" vorliegt, erlaubt dieser nicht, dass man die gesamt HTML-Seite
durch ein get-request erhalten kann. Man erhaltet bei der get-request gelegentlich nur den ersten Paragraphen. 
Diese Funktion dient dazu da, dass man bei der HTML-Seite des Artikels die <p>-Tags bei "article-body" erhält.
Wenn man die URL der Seite im Terminal eingibt, öffnet sich bei mir der Microsoft Edge Browser, der dann den Inhalt 
auslesen wird
wichtig ist, dass man 5 Sekunden Zeit hat, die Datenschutzerklärung zu ablehnen bzw. anzunehmen

Das hier ist nur ein temporärer Fix, um einfach mal irgendwelche Daten zu erhalten.
Man könnte später mittels Javascript vielleicht austricksen

https://www.ionos.at/digitalguide/websites/web-entwicklung/web-scraping-mit-python/
Bei der Überschrift "Technische Beschränkungen des Web Scrapings" wird genauer erläutert, wie get-requests oder
ähnlicher Art das Web Scraping verhindert wird, bzw. nur ein beschränkter Teil des Inhalts zu verfügen stellt

"""
def extract_article_content(url):
    # Pfad zu Ihrem EdgeDriver (passen Sie dies an den Speicherort Ihres EdgeDrivers an)
    driver_path = 'C:/Users/themi/Documents/msedgedriver.exe'
    service = Service(driver_path)
    
    # Erstellen Sie eine Edge WebDriver-Instanz mit dem Service
    driver = webdriver.Edge(service=service)
    
    # Öffnen Sie die URL
    driver.get(url)
    
    # Warten Sie einige Sekunden, damit die Seite vollständig geladen wird
    time.sleep(5)
    
    # Extrahieren Sie den Artikelinhalt
    try:
        # Anpassen des Selektors je nach Seitenstruktur
        article_body = driver.find_element(By.CLASS_NAME, 'article-body')
        
        paragraphs = article_body.find_elements(By.TAG_NAME, 'p')
        content = [para.text for para in paragraphs]
        
        print(f"Anzahl der gefundenen Paragraphen: {len(paragraphs)}")
        return content
    except Exception as e:
        print(f"Fehler beim Extrahieren des Inhalts: {e}")
        return []
    finally:
        # Schließen Sie den WebDriver
        driver.quit()

url = input("Geben Sie bitte eine URL ein: ")
article_content = extract_article_content(url)
for i, paragraph in enumerate(article_content):
    print(f"Paragraph {i+1}: {paragraph}")


