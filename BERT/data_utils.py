import os
import re
from collections import defaultdict

import pandas as pd
import sqlalchemy
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

DB_URL = os.getenv("DB_URL", "mysql+mysqlconnector://root@localhost/diplomarbeit")
MIN_ARTICLES_PER_AUTHOR = 10

# derStandard-Artikel enden mit einer Signatur wie "(Jakob Pflügl, 21.8.2024)".
# Bleibt sie im Text, kann das Modell den Namen einfach ablesen statt den Schreibstil zu lernen.
SIGNATURE_PATTERN = re.compile(r"\([^()]{1,150},\s*\d{1,2}\.\s?\d{1,2}\.\s?\d{4}\)")


def strip_signature(text):
    """Entfernt die Autorensignatur (Name, Datum) aus dem Artikeltext."""
    if not isinstance(text, str):
        return ""
    return SIGNATURE_PATTERN.sub("", text).strip()


def load_articles(engine=None, remove_signature=True):
    """Lädt Artikel mit Autor aus MySQL und behält nur Autoren mit genug Artikeln."""
    engine = engine or sqlalchemy.create_engine(DB_URL)
    query = """
    SELECT a.id as article_id, a.content, auth.name as author
    FROM articles a
    JOIN placeholder p ON a.id = p.article_id
    JOIN authors auth ON p.author_id = auth.id
    """
    df = pd.read_sql(query, engine)
    df = df[df['author'] != 'kein Autor']

    author_counts = df['author'].value_counts()
    authors_filtered = author_counts[author_counts >= MIN_ARTICLES_PER_AUTHOR].index
    df = df[df['author'].isin(authors_filtered)].reset_index(drop=True)

    if remove_signature:
        df['content'] = df['content'].apply(strip_signature)
    return df


def split_by_author(df, test_size=0.2, random_state=42):
    """
    Train/Test-Split pro Autor (80/20) auf Artikelebene.
    Ein Artikel mit mehreren Autoren landet komplett im Testset, sobald er bei einem Autor im Test ist,
    damit derselbe Text nie in Training und Test gleichzeitig vorkommt.
    """
    author_to_articles = defaultdict(set)
    for article_id, author in zip(df['article_id'], df['author']):
        author_to_articles[author].add(article_id)

    test_article_ids = set()
    for author, article_ids in author_to_articles.items():
        # list(set) statt sorted(): genau dieselbe Reihenfolge wie beim Training des gespeicherten Checkpoints,
        # sonst würde evaluate.py andere (schon trainierte) Artikel als Testdaten nehmen
        _, test_ids = train_test_split(list(article_ids), test_size=test_size, random_state=random_state)
        test_article_ids.update(test_ids)

    train_df = df[~df['article_id'].isin(test_article_ids)].reset_index(drop=True)
    test_df = df[df['article_id'].isin(test_article_ids)].reset_index(drop=True)

    # Autoren, die nur noch im Testset vorkommen, kann das Modell nicht kennen
    test_df = test_df[test_df['author'].isin(set(train_df['author']))].reset_index(drop=True)

    label_encoder = LabelEncoder()
    train_df['author_id'] = label_encoder.fit_transform(train_df['author'])
    test_df['author_id'] = label_encoder.transform(test_df['author'])
    return train_df, test_df, label_encoder
