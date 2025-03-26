import pandas as pd
from sqlalchemy import create_engine, text
import os
import sys
from datetime import datetime, time, timedelta
from dateutil import parser
import re

# Optional: Um SQLAlchemy-Warnungen zu stummschalten (oder auf 2.0 vorbereiten)
os.environ['SQLALCHEMY_WARN_20'] = '1'

def clean_author_name(author):
    """Bereinigt Autorennamen von Ortsangaben und formatiert sie einheitlich"""
    if pd.isnull(author) or not isinstance(author, str):
        return author

    # Entferne Ortsangaben wie "aus Wien", "aus Deutschland"
    author = re.sub(r' aus [A-ZÄÖÜ][a-zäöüß]+', '', author).strip()
    
    # Setze Autoren in Anführungszeichen
    return f'"{author}"'

def clean_article_content(content):
    """Bereinigt den Artikelinhalt von nicht relevanten Informationen"""
    if pd.isnull(content) or not isinstance(content, str):
        return content

    # Entferne Autorenangaben mit Datum am Ende
    content = re.sub(r'\([A-Za-z\s,\.und]+\d{1,2}\.\d{1,2}\.\d{4}\)$', '', content).strip()
    
    # Entferne Agenturangaben
    content = re.sub(r'\(?(Reuters|APA|dpa|red)(, [\d\.]+)?\)?$', '', content).strip()
    
    # Entferne Redaktionshinweise
    content = re.sub(r'\(red\)', '', content, flags=re.IGNORECASE).strip()
    
    # Entferne Interaktionsaufforderungen
    content = re.sub(r'Posten Sie im Forum[.!?]', '', content, flags=re.IGNORECASE).strip()
    
    return content

def split_authors(author_str):
    """Trennt Autorennamen und gibt sie als einen String in Anführungszeichen zurück"""
    if pd.isnull(author_str) or not isinstance(author_str, str):
        return '""'
        
    # Ersetze verschiedene Trennzeichen mit einem einheitlichen Komma
    author_str = re.sub(r'\s*(,|oder|&|/|und)\s*', ',', author_str)
    
    # Trenne die Autoren und entferne Leerzeichen
    authors = [author.strip() for author in author_str.split(',') if author.strip()]
    
    # Setze jeden Autor in Anführungszeichen und verbinde sie mit Kommas
    quoted_authors = [f'"{author}"' for author in authors]
    
    # Verbinde alle Autoren mit Kommas und setze das Ganze in Anführungszeichen
    return f'"{", ".join(quoted_authors)}"'

# Get CSV file path from command line argument or environment variable
if len(sys.argv) > 1:
    csv_file = sys.argv[1]
elif 'CRAWLER_CSV_PATH' in os.environ:
    csv_file = os.environ['CRAWLER_CSV_PATH']
else:
    csv_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'crawler', 'urls_today.csv')

print(f"Using CSV file: {csv_file}")

# MySQL-Datenbankverbindung mit korrektem Port
engine = create_engine('mysql+mysqlconnector://root:1234@localhost:33061/diplomarbeit')

# CSV-Datei laden
try:
    df = pd.read_csv(csv_file)
    print(f"Successfully loaded {len(df)} rows from CSV")
except Exception as e:
    print(f"Error loading CSV file {csv_file}: {e}")
    sys.exit(1)

# Ensure correct column names
if len(df.columns) == 4:
    df.columns = ["url", "lastmod", "author", "content"]

# Custom function to parse each date string
def parse_dates(date_str):
    try:
        # Use dateutil.parser to handle timezone and convert to UTC
        return parser.parse(date_str)
    except Exception:
        return pd.NaT

# Convert lastmod to datetime using the custom parser
df['lastmod'] = df['lastmod'].apply(parse_dates)

# Check for any NaT values after parsing
nat_count = df['lastmod'].isna().sum()
if nat_count > 0:
    print(f"Warning: Found {nat_count} invalid date values")

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

# Convert lastmod to naive datetime (remove timezone information)
df['lastmod'] = df['lastmod'].dt.tz_localize(None)

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
    else:
        # Filtere die DataFrame-Zeilen basierend auf None-Werten in 'lastmod'
        df = df[df['lastmod'].notna()]
        print(f"Processing {len(df)} new articles")

        for index, row in df.iterrows():
            # Artikel in die articles Tabelle einfügen
            connection.execute(
                text("""
                    INSERT INTO articles (url, lastmod, content) 
                    VALUES (:url, :lastmod, :content)
                """), {
                    'url': row['url'],
                    'lastmod': row['lastmod'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['lastmod']) else None,
                    'content': row['content']
                }
            )
            
            # Hole die ID des neu eingefügten Artikels
            article_id = connection.execute(text("""
                SELECT LAST_INSERT_ID()
            """)).scalar()
            
            # Verarbeite die Autoren
            # Entferne die äußeren Anführungszeichen und teile die Autoren
            authors_str = row['author'].strip('"')  # Entferne äußere Anführungszeichen
            authors = [auth.strip('"') for auth in authors_str.split('", "')]  # Teile die einzelnen Autoren
            
            for author in authors:
                # Überprüfe, ob der Autor bereits existiert
                result = connection.execute(
                    text("""
                        SELECT id FROM authors WHERE name = :name
                    """), {'name': author}
                ).fetchone()

                if result:
                    # Autor existiert, verwende die bestehende ID
                    author_id = result['id']
                else:
                    # Autor existiert nicht, füge ihn hinzu
                    connection.execute(
                        text("""
                            INSERT INTO authors (name) VALUES (:name)
                        """), {'name': author}
                    )
                    # Hole die ID des neu eingefügten Autors
                    author_id = connection.execute(text("""
                        SELECT LAST_INSERT_ID()
                    """)).scalar()

                # Verknüpfe Artikel und Autor in der placeholder Tabelle
                connection.execute(
                    text("""
                        INSERT IGNORE INTO placeholder (article_id, author_id) 
                        VALUES (:article_id, :author_id)
                    """), {
                        'article_id': article_id,
                        'author_id': author_id
                    }
                )
                
        print("Neue Artikel und Autoren wurden erfolgreich eingefügt.")
