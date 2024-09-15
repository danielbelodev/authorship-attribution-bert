import pandas as pd
from sqlalchemy import create_engine, text
import os
from datetime import datetime, time, timedelta

# Optional: Um SQLAlchemy-Warnungen zu stummschalten (oder auf 2.0 vorbereiten)
os.environ['SQLALCHEMY_WARN_20'] = '1'

# CSV-Dateipfad
csv_file = 'C:\\Users\\Daniel\\Documents\\Arbeit\\diplomarbeit\\daten.csv'

# MySQL-Datenbankverbindung
engine = create_engine('mysql+mysqlconnector://root:1234@localhost/diplomarbeit')

# CSV-Datei laden
df = pd.read_csv(csv_file)

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
        print("Neue Artikel wurden erfolgreich eingefügt.")
