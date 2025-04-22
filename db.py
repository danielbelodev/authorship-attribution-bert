import csv
import re
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, Table
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.dialects.mysql import MEDIUMTEXT

# SQLAlchemy Setup mit korrektem Import
Base = declarative_base()

# Definiere die Many-to-Many Beziehungstabelle für Artikel und Autoren
article_author_association = Table(
    'placeholder', Base.metadata,
    Column('article_id', Integer, ForeignKey('articles.id'), primary_key=True),
    Column('author_id', Integer, ForeignKey('authors.id'), primary_key=True)  # Geändert von 'author.id' zu 'authors.id'
)

# Definiere die Artikel-Klasse
class Article(Base):
    __tablename__ = 'articles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, nullable=False)
    lastmod = Column(String(100))
    content = Column(MEDIUMTEXT)
    
    # Beziehung zu Autoren über Placeholder-Tabelle
    authors = relationship("Author", secondary=article_author_association, back_populates="articles")
    
    def __repr__(self):
        return f"<Article(id={self.id}, url='{self.url[:50]}...')>"

# Definiere die Autor-Klasse - Tabellenname auf 'authors' geändert
class Author(Base):
    __tablename__ = 'authors'  # Geändert von 'author' zu 'authors'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    
    # Beziehung zu Artikeln über Placeholder-Tabelle
    articles = relationship("Article", secondary=article_author_association, back_populates="authors")
    
    def __repr__(self):
        return f"<Author(id={self.id}, name='{self.name}')>"

def extract_authors(author_text):
    """
    Extrahiert die Autoren aus einem Text basierend auf verschiedenen Kriterien:
    - Ortsangaben ("aus Stadt")
    - Zusammenschreibungen (ohne Leerzeichen zwischen Namen)
    - Komma-Trennungen
    - "und"-Trennungen
    - "Verfasst von"-Präfix
    """
    # Entferne "Verfasst von" am Anfang
    author_text = re.sub(r'^Verfasst von\s+', '', author_text.strip())
    
    # Initialisiere die Liste der Autoren
    authors = []
    
    # Prüfe zuerst auf Komma-Trennung und "und"-Trennung
    if ',' in author_text or ' und ' in author_text:
        # Ersetze " und " durch ", " für einheitliche Verarbeitung
        author_text = author_text.replace(' und ', ', ')
        # Teile nach Komma auf
        raw_authors = [a.strip() for a in author_text.split(',')]
        
        for raw_author in raw_authors:
            # Prüfe auf Ortsangabe "aus [Stadt]"
            aus_match = re.search(r'(.*?)\s+aus\s+(.*)', raw_author)
            if aus_match:
                authors.append(aus_match.group(1).strip())
            else:
                authors.append(raw_author.strip())
    else:
        # Prüfe auf Ortsangabe "aus [Stadt]"
        aus_matches = re.findall(r'(.*?)\s+aus\s+[^\s]+(?:\s+|$)', author_text)
        if aus_matches:
            # Wenn Ortsangaben gefunden wurden
            current_pos = 0
            for match in re.finditer(r'(.*?)\s+aus\s+[^\s]+(?:\s+|$)', author_text):
                author_name = match.group(1).strip()
                if author_name:
                    authors.append(author_name)
                current_pos = match.end()
            
            # Prüfen, ob noch Text nach der letzten Ortsangabe übrig ist
            if current_pos < len(author_text):
                rest = author_text[current_pos:].strip()
                if rest:
                    authors.append(rest)
        else:
            # Versuche Namen zu trennen, die ohne Leerzeichen zusammengeschrieben sind
            # Suche nach Mustern wie "MaxMustermann" oder "MaxMustermannKendridMayer"
            potential_names = re.findall(r'([A-Z][a-z]+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', author_text)
            if potential_names:
                for first_name, last_name in potential_names:
                    authors.append(f"{first_name} {last_name}")
            else:
                # Wenn keine der obigen Trennungen funktioniert, füge den gesamten Text als einen Autor hinzu
                authors.append(author_text)
    
    # Nachbearbeitung: Entferne leere Einträge und doppelte Leerzeichen
    processed_authors = []
    for author in authors:
        author = re.sub(r'\s+', ' ', author).strip()
        if author and author not in processed_authors:
            processed_authors.append(author)
    
    return processed_authors

def main():
    # Korrekt formatierte Datenbank-URL für SQLAlchemy
    DATABASE_URL = "mysql+pymysql://root:1234@localhost/test"
    
    # CSV-Dateiname
    csv_filename = 'ks.csv'
    
    try:
        # Engine erstellen
        engine = create_engine(DATABASE_URL)
        
        # Wir erstellen die Tabellen NICHT automatisch, da sie bereits existieren
        # und die bestehende Struktur genutzt werden soll
        # Base.metadata.create_all(engine)
        
        # Session erstellen
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Dictionary für bereits vorhandene Autoren (Name -> Objekt)
            existing_authors = {}
            
            # Lade bereits vorhandene Autoren
            for author in session.query(Author).all():
                existing_authors[author.name] = author
            
            # CSV-Datei öffnen und verarbeiten
            with open(csv_filename, 'r', encoding='utf-8') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                article_count = 0
                
                for row in csv_reader:
                    # Extrahiere Daten aus CSV-Zeile
                    url = row['url']
                    lastmod = row['lastmod']
                    content = row['content']
                    author_text = row['author']
                    
                    # Erstelle neuen Artikel
                    article = Article(url=url, lastmod=lastmod, content=content)
                    session.add(article)
                    session.flush()  # Damit wir die article_id sofort bekommen
                    
                    # Extrahiere Autoren
                    authors = extract_authors(author_text)
                    
                    # Verarbeite jeden Autor
                    for author_name in authors:
                        # Prüfe, ob der Autor bereits in der Datenbank existiert
                        if author_name in existing_authors:
                            author = existing_authors[author_name]
                        else:
                            # Erstelle neuen Autor
                            author = Author(name=author_name)
                            session.add(author)
                            session.flush()  # Damit wir die author_id sofort bekommen
                            existing_authors[author_name] = author
                        
                        # Füge den Autor zum Artikel hinzu
                        article.authors.append(author)
                    
                    article_count += 1
                    
                    # Committet in Batches von 50, um die Datenbank nicht zu überlasten
                    if article_count % 50 == 0:
                        session.commit()
                        print(f"{article_count} Artikel verarbeitet...")
            
            # Endgültiger Commit aller Änderungen
            session.commit()
            print(f"Datenimport abgeschlossen. {article_count} Artikel und {len(existing_authors)} Autoren wurden verarbeitet.")
            
        except Exception as e:
            session.rollback()
            print(f"Fehler beim Datenimport: {e}")
        
        finally:
            session.close()
            print("Datenbankverbindung wurde geschlossen.")
            
    except Exception as e:
        print(f"Fehler bei der Datenbankverbindung: {e}")

if __name__ == "__main__":
    main()