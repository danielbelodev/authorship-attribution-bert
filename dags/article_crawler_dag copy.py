from datetime import datetime, timedelta, time
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
import requests
from bs4 import BeautifulSoup
import csv

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
dag = DAG(
    'article_crawler',
    default_args=default_args,
    description='Crawl articles and load to database',
    schedule_interval=timedelta(days=1),  # Run daily
    start_date=datetime(2023, 1, 1),
    catchup=False,
)

# Get the path to the DAG file
dag_path = os.path.dirname(os.path.abspath(__file__))
# Get the workspace path (parent of dags directory)
workspace_path = os.path.dirname(dag_path)

# Define the file paths
csv_file_path = os.path.expanduser('~/airflow_clean/data/urls.csv')

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
    with open(file_path, "a", newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(data)
    print(f"Saved {len(data)} new URLs to {file_path}")

def read_seen_urls(file_path):
    seen_urls = set()
    try:
        with open(file_path, newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader, None)  # Skip header if it exists
            for row in reader:
                if row:  # Skip empty rows
                    seen_urls.add(row[0])
    except FileNotFoundError:
        # Create the file with header if it doesn't exist
        with open(file_path, "w", newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["url", "lastmod", "author", "content"])
    return seen_urls

def crawl_sitemap(url, csv_path):
    collected_data = []
    seen_urls = read_seen_urls(csv_path)

    print(f"Crawling Sitemap URL: {url}")

    try:
        response = requests.get(url, cookies=COOKIES)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching sitemap {url}: {e}")
        return 0

    sitemap_content = response.content
    soup = BeautifulSoup(sitemap_content, 'xml')
    url_tags = soup.find_all('url')

    if not url_tags:
        return 0

    for url_tag in url_tags:
        loc = url_tag.find('loc').text
        if loc in seen_urls:
            continue

        lastmod = url_tag.find('lastmod').text if url_tag.find('lastmod') else ""
        print(f"Processing Article URL: {loc}")
        content, author = extract_article_content(loc)

        # Only add to collected_data if content is not empty
        if content:
            collected_data.append((loc, lastmod, author, content))
            seen_urls.add(loc)

    # Save collected data to CSV after processing this sitemap
    if collected_data:
        save_to_csv(csv_path, collected_data)

    return len(collected_data)

def crawl_task(**kwargs):
    """Task to crawl sitemaps and extract article content"""
    # Determine the current year and month
    current_year = datetime.now().year
    current_month = datetime.now().month

    # Set the start year (modify as needed)
    start_year = 2025

    # Calculate days to go back (default to 7 days)
    days_back = kwargs.get('days_back', 7)
    
    # For testing or initial runs, we might want to limit to more recent sitemaps
    target_date = datetime.now() - timedelta(days=days_back)
    target_year = target_date.year
    target_month = target_date.month
    
    # Generate sitemap URLs for the specified time period
    sitemap_urls = []
    for year in range(target_year, current_year + 1):
        for month in range(1, 13):
            if (year == target_year and month < target_month) or (year == current_year and month > current_month):
                continue
            sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{year}-{month:02}.xml"
            sitemap_urls.append(sitemap_url)

    # Initialize counters
    total_new_articles = 0
    
    # Crawl each sitemap URL
    for sitemap_url in sitemap_urls:
        new_articles = crawl_sitemap(sitemap_url, csv_file_path)
        total_new_articles += new_articles
        
    return f"Collected {total_new_articles} new articles"

def process_and_load_data(**kwargs):
    """Task to process the CSV data and load it into the database"""
    # MySQL-Datenbankverbindung
    engine = create_engine('mysql+mysqlconnector://root:1234@localhost/diplomarbeit')
    
    # CSV-Datei laden
    try:
        df = pd.read_csv(csv_file_path)
    except pd.errors.EmptyDataError:
        print("CSV file is empty.")
        return "No data to process"
    
    # Datumsspalte in datetime konvertieren (Fehlerhafte Werte werden zu NaT)
    df['lastmod'] = pd.to_datetime(df['lastmod'], errors='coerce', utc=True)

    # Convert 'lastmod' to naive datetime (remove timezone information)
    df['lastmod'] = df['lastmod'].dt.tz_localize(None)

    # Funktion, um fehlerhafte Zeit zu überprüfen und zu korrigieren
    def fix_lastmod_datetime(dt):
        if pd.isnull(dt):  # Fehlerhaftes Datum ignorieren
            return None
        try:
            # Überprüfen, ob die Zeit fehlt oder fehlerhaft ist
            if dt.hour is None or dt.minute is None or dt.second is None:
                # Setze die Zeit auf 00:00:00
                return datetime.combine(dt.date(), time(0, 0, 0))
            return dt  # Wenn alles korrekt ist, Datum und Uhrzeit zurückgeben
        except:
            # Wenn ein Fehler auftritt, das Datum ignorieren
            return None

    # Funktion zum generellen Aufrunden auf die nächste volle Sekunde
    def round_up_to_next_second(dt):
        if pd.isnull(dt):
            return None
        # Runde die Sekunde auf, indem eine Sekunde hinzugefügt wird und dann die Mikrosekunden entfernt werden
        return (dt + timedelta(seconds=1)).replace(microsecond=0) if dt.microsecond > 0 else dt

    # Wende die Funktionen auf die 'lastmod'-Spalte an
    df['lastmod'] = df['lastmod'].apply(fix_lastmod_datetime)
    df['lastmod'] = df['lastmod'].apply(round_up_to_next_second)

    # Entferne Mikrosekunden aus der 'lastmod'-Spalte
    df['lastmod'] = df['lastmod'].apply(lambda x: x.replace(microsecond=0) if pd.notnull(x) else x)

    # Maximale Länge für Autorennamen auf 255 Zeichen begrenzen
    max_length = 255
    df['author'] = df['author'].apply(lambda x: x[:max_length] if isinstance(x, str) else x)

    # Verbindung zur Datenbank herstellen
    with engine.connect() as connection:
        # Hole die letzte eingefügte URL
        last_url = connection.execute(text("""
            SELECT url FROM articles ORDER BY id DESC LIMIT 1
        """)).fetchone()

        if last_url:
            last_url = last_url['url']

        # Filtere die DataFrame-Zeilen basierend auf der letzten eingefügten URL
        if last_url:
            df = df[df['url'] > last_url]  # Nur URLs, die nach der letzten URL kommen, werden verarbeitet

        # Überprüfen, ob es überhaupt neue Artikel gibt
        if df.empty:
            print("Keine neuen Artikel zum Einfügen.")
            return "No new articles to insert"
        else:
            # Filtere die DataFrame-Zeilen basierend auf None-Werten in 'lastmod'
            df = df[df['lastmod'].notna()]
            inserted_count = 0

            for index, row in df.iterrows():
                # Überprüfen, ob der Autor bereits existiert
                result = connection.execute(
                    text("""
                        SELECT id FROM authors WHERE name = :name
                    """), {'name': row['author']}
                ).fetchone()

                if result:
                    # Autor existiert, verwende die bestehende ID
                    author_id = result['id']
                else:
                    # Autor existiert nicht, füge ihn hinzu und hole die ID
                    connection.execute(
                        text("""
                            INSERT INTO authors (name) VALUES (:name)
                        """), {'name': row['author']}
                    )
                    # Hole die ID des neu eingefügten Autors
                    author_id = connection.execute(
                        text("""
                            SELECT id FROM authors WHERE name = :name
                        """), {'name': row['author']}
                    ).fetchone()['id']

                # Article in die articles Tabelle einfügen mit der entsprechenden author_id
                connection.execute(
                    text("""
                        INSERT INTO articles (url, lastmod, content, author_id)
                        VALUES (:url, :lastmod, :content, :author_id)
                    """), {
                        'url': row['url'],
                        'lastmod': row['lastmod'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['lastmod']) else None,
                        'content': row['content'],
                        'author_id': author_id
                    }
                )
                inserted_count += 1
            
            return f"Successfully inserted {inserted_count} new articles"

# Define the tasks
crawl_articles_task = PythonOperator(
    task_id='crawl_articles',
    python_callable=crawl_task,
    op_kwargs={'days_back': 30},  # Adjust as needed
    dag=dag,
)

load_to_db_task = PythonOperator(
    task_id='load_to_database',
    python_callable=process_and_load_data,
    dag=dag,
)

# Set task dependencies
crawl_articles_task >> load_to_db_task 