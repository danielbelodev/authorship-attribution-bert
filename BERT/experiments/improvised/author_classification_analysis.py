import pandas as pd
import numpy as np
import torch
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report
import sqlalchemy
import logging
import os
from tqdm import tqdm
import json
from transformers import BertTokenizer, BertForSequenceClassification

# Importiere die predict_author-Funktion aus predict.py
from predict import predict_author, clean_text, load_model

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('author_classification_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Gerät für Inferenz festlegen
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"Using device: {device}")

def fetch_data_from_mysql(min_articles_per_author=2):
    """
    Lädt Artikel und Autoren aus der MySQL-Datenbank und filtert Autoren 
    mit zu wenigen Artikeln.
    
    Args:
        min_articles_per_author: Minimale Anzahl von Artikeln pro Autor
        
    Returns:
        DataFrame mit Artikeln und deren Autoren
    """
    try:
        # Datenbankverbindung mit explizitem Host und Port
        engine = sqlalchemy.create_engine(
            os.getenv("DB_URL", "mysql+mysqlconnector://root@127.0.0.1:3306/diplomarbeit"),
            connect_args={'use_pure': True}  # Use pure Python implementation
        )
        
        # Test connection before proceeding
        try:
            engine.connect()
            logger.info("Successfully connected to database")
        except Exception as e:
            logger.error(f"Could not connect to database: {str(e)}")
            logger.error("Please ensure that:")
            logger.error("1. MySQL server is running (sudo service mysql status)")
            logger.error("2. MySQL is accepting connections on 127.0.0.1:3306")
            logger.error("3. User 'root' has correct permissions")
            logger.error("4. DB_URL (Umgebungsvariable) enthält die richtigen Zugangsdaten")
            logger.error("5. Database 'diplomarbeit' exists")
            raise
        
        # Artikel und Autoren abrufen
        query = """
        SELECT articles.id, articles.content, COALESCE(authors.name, 'kein Autor') AS author
        FROM articles
        LEFT JOIN authors ON articles.author_id = authors.id
        WHERE authors.name IS NOT NULL
        """
        
        # Verbindung herstellen und Daten abrufen
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
            
        logger.info(f"Daten aus MySQL geladen: {len(df)} Artikel")
        
        # Nur Artikel mit bekanntem Autor verwenden
        df = df[df['author'] != 'kein Autor']
        logger.info(f"Artikel mit bekanntem Autor: {len(df)}")
        
        # Autoren mit zu wenigen Artikeln entfernen
        author_counts = df['author'].value_counts()
        valid_authors = author_counts[author_counts >= min_articles_per_author].index
        df = df[df['author'].isin(valid_authors)]
        logger.info(f"Artikel nach Filterung (mind. {min_articles_per_author} pro Autor): {len(df)}")
        logger.info(f"Anzahl Autoren für Analyse: {len(valid_authors)}")
        
        # Textbereinigung anwenden
        df['content'] = df['content'].apply(clean_text)
        
        return df
        
    except Exception as e:
        logger.error(f"Fehler beim Datenbankzugriff: {str(e)}")
        raise

def analyze_author_classification(df, model=None, tokenizer=None, classes=None, sample_size=None):
    """
    Führt eine Autorenklassifikation durch und erstellt eine Konfusionsmatrix.
    
    Args:
        df: DataFrame mit Artikeln und Autoren
        model, tokenizer, classes: Optional, wenn nicht angegeben werden sie geladen
        sample_size: Optional, begrenzt die Anzahl der zu analysierenden Artikel
        
    Returns:
        Tuple mit (true_authors, predicted_authors, confusion_matrix)
    """
    # Modell, Tokenizer und Klassen laden, falls nicht übergeben
    if model is None or tokenizer is None or classes is None:
        model, tokenizer, classes = load_model()
    
    # Optional: Begrenze die Anzahl der Artikel für die Analyse
    if sample_size is not None and sample_size < len(df):
        # Stratifizierte Stichprobe: Gleichmäßige Verteilung über Autoren
        sampled_df = pd.DataFrame()
        for author in df['author'].unique():
            author_df = df[df['author'] == author]
            n_samples = min(sample_size // len(df['author'].unique()), len(author_df))
            sampled_df = pd.concat([sampled_df, author_df.sample(n=n_samples, random_state=42)])
        df = sampled_df
        logger.info(f"Reduzierte Stichprobe für Analyse: {len(df)} Artikel")

    # Listen für die tatsächlichen und vorhergesagten Autoren
    true_authors = []
    predicted_authors = []
    confidences = []
    
    # Fortschrittsbalken für die Verarbeitung
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Verarbeite Artikel"):
        article_id = row['id']
        content = row['content']
        true_author = row['author']
        
        # Vorhersage
        try:
            pred_author, similarity_scores, confidence = predict_author(
                content, model, tokenizer, classes
            )
            
            true_authors.append(true_author)
            predicted_authors.append(pred_author)
            confidences.append(confidence)
            
            # Logging für falsche Vorhersagen mit hoher Konfidenz
            if pred_author != true_author and confidence > 0.7:
                logger.warning(
                    f"Hohe Konfidenz bei Fehlklassifikation: Artikel {article_id}, "
                    f"Wahrer Autor: {true_author}, Vorhergesagt: {pred_author}, Konfidenz: {confidence:.3f}"
                )
                
        except Exception as e:
            logger.error(f"Fehler bei Artikel {article_id}: {str(e)}")
            continue
    
    # Gesamtgenauigkeit berechnen
    accuracy = sum(1 for t, p in zip(true_authors, predicted_authors) if t == p) / len(true_authors)
    logger.info(f"Gesamtgenauigkeit: {accuracy:.3f}")
    
    # Durchschnittliche Konfidenz
    avg_confidence = sum(confidences) / len(confidences)
    logger.info(f"Durchschnittliche Konfidenz: {avg_confidence:.3f}")
    
    # Konfusionsmatrix erstellen
    unique_authors = sorted(set(true_authors).union(set(predicted_authors)))
    cm = confusion_matrix(
        true_authors, 
        predicted_authors, 
        labels=unique_authors
    )
    
    # Ausführlichen Klassifikationsbericht erstellen
    report = classification_report(
        true_authors, 
        predicted_authors, 
        labels=unique_authors,
        target_names=unique_authors,
        digits=3
    )
    logger.info(f"Klassifikationsbericht:\n{report}")
    
    return true_authors, predicted_authors, cm, unique_authors

def plot_confusion_matrix(cm, classes, title='Konfusionsmatrix der Autorenklassifikation',
                          normalize=True, figsize=(14, 12), output_file='author_confusion_matrix.png'):
    """
    Erzeugt eine Visualisierung der Konfusionsmatrix.
    
    Args:
        cm: Konfusionsmatrix
        classes: Liste der Klassennamen (Autoren)
        title: Titel des Plots
        normalize: Ob die Matrix normalisiert werden soll
        figsize: Größe der Abbildung
        output_file: Dateiname zum Speichern der Abbildung
    """
    plt.figure(figsize=figsize)
    
    # Normalisierung der Konfusionsmatrix
    if normalize:
        cm_sum = cm.sum(axis=1)[:, np.newaxis]
        cm_normalized = np.zeros_like(cm, dtype=float)
        for i in range(cm.shape[0]):
            if cm_sum[i, 0] > 0:
                cm_normalized[i, :] = cm[i, :] / cm_sum[i, 0]
        cm_display = cm_normalized
        fmt = '.2f'
    else:
        cm_display = cm
        fmt = 'd'
    
    # Erstellen des Heatmaps
    sns.heatmap(
        cm_display, 
        annot=True, 
        fmt=fmt, 
        cmap='Blues',
        xticklabels=classes, 
        yticklabels=classes
    )
    
    plt.ylabel('Tatsächlicher Autor')
    plt.xlabel('Vorhergesagter Autor')
    plt.title(title)
    plt.tight_layout()
    
    # Speichern der Abbildung
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    logger.info(f"Konfusionsmatrix gespeichert unter {output_file}")
    
    return plt.gcf()

def create_author_analysis_report(df, true_authors, predicted_authors, confidences, output_dir='analysis_results'):
    """
    Erstellt einen detaillierten Bericht zur Autorenklassifikation.
    
    Args:
        df: Originales DataFrame mit Artikeln
        true_authors: Liste der tatsächlichen Autoren
        predicted_authors: Liste der vorhergesagten Autoren
        confidences: Liste der Konfidenzwerte
        output_dir: Verzeichnis für die Ausgabedateien
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Genauigkeit pro Autor
    author_accuracy = {}
    for author in set(true_authors):
        # Indizes finden, wo der wahre Autor dieser Autor ist
        indices = [i for i, a in enumerate(true_authors) if a == author]
        # Anzahl korrekter Vorhersagen
        correct = sum(1 for i in indices if predicted_authors[i] == author)
        # Genauigkeit
        accuracy = correct / len(indices) if indices else 0
        author_accuracy[author] = accuracy
    
    # Nach Genauigkeit sortieren
    sorted_authors = sorted(author_accuracy.items(), key=lambda x: x[1], reverse=True)
    
    # 2. Durchschnittliche Konfidenz pro Autor
    author_confidence = {}
    for author in set(true_authors):
        # Indizes finden, wo der wahre Autor dieser Autor ist
        indices = [i for i, a in enumerate(true_authors) if a == author]
        # Durchschnittliche Konfidenz
        avg_conf = sum(confidences[i] for i in indices) / len(indices) if indices else 0
        author_confidence[author] = avg_conf
    
    # 3. Detaillierte Ergebnisse in JSON speichern
    results = {
        "overall_accuracy": sum(1 for t, p in zip(true_authors, predicted_authors) if t == p) / len(true_authors),
        "overall_avg_confidence": sum(confidences) / len(confidences),
        "author_accuracy": author_accuracy,
        "author_confidence": author_confidence,
        "best_authors": [{"author": a, "accuracy": acc} for a, acc in sorted_authors[:5]],
        "worst_authors": [{"author": a, "accuracy": acc} for a, acc in sorted_authors[-5:]]
    }
    
    with open(f"{output_dir}/classification_results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 4. Genauigkeit pro Autor visualisieren
    plt.figure(figsize=(12, 8))
    authors = [a for a, _ in sorted_authors[:15]]  # Top 15 Autoren
    accuracies = [acc for _, acc in sorted_authors[:15]]
    
    bars = plt.bar(authors, accuracies, color='skyblue')
    plt.xlabel('Autor')
    plt.ylabel('Klassifikationsgenauigkeit')
    plt.title('Top 15 Autoren nach Klassifikationsgenauigkeit')
    plt.xticks(rotation=45, ha='right')
    
    # Werte über den Balken anzeigen
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width()/2.,
            height + 0.01,
            f'{height:.2f}',
            ha='center', va='bottom'
        )
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/author_accuracy.png", dpi=300)
    
    # 5. Bericht als Textdatei
    with open(f"{output_dir}/analysis_report.txt", 'w', encoding='utf-8') as f:
        f.write("Bericht zur Autorenklassifikation\n")
        f.write("===============================\n\n")
        f.write(f"Gesamtzahl analysierter Artikel: {len(true_authors)}\n")
        f.write(f"Anzahl einzigartiger Autoren: {len(set(true_authors))}\n")
        f.write(f"Gesamtgenauigkeit: {results['overall_accuracy']:.3f}\n")
        f.write(f"Durchschnittliche Konfidenz: {results['overall_avg_confidence']:.3f}\n\n")
        
        f.write("Top 5 Autoren mit höchster Genauigkeit:\n")
        for item in results["best_authors"]:
            f.write(f"  {item['author']}: {item['accuracy']:.3f}\n")
        
        f.write("\nSchlechteste 5 Autoren nach Genauigkeit:\n")
        for item in results["worst_authors"]:
            f.write(f"  {item['author']}: {item['accuracy']:.3f}\n")
    
    logger.info(f"Detaillierter Analysebericht erstellt im Verzeichnis {output_dir}")

def main():
    """Hauptfunktion zur Ausführung der Analyse"""
    # Parameter für die Analyse
    min_articles_per_author = 3  # Minimale Anzahl von Artikeln pro Autor
    sample_size = 500  # Maximale Anzahl zu analysierender Artikel (None für alle)
    
    # 1. Daten aus MySQL laden
    logger.info("Lade Daten aus MySQL...")
    df = fetch_data_from_mysql(min_articles_per_author)
    
    # 2. Modell laden
    logger.info("Lade BERT-Modell...")
    model, tokenizer, classes = load_model()
    
    # 3. Autorenklassifikation durchführen
    logger.info("Führe Autorenklassifikation durch...")
    true_authors, predicted_authors, cm, unique_authors = analyze_author_classification(
        df, model, tokenizer, classes, sample_size
    )
    
    # 4. Konfusionsmatrix visualisieren
    logger.info("Erstelle Konfusionsmatrix-Visualisierung...")
    # Erste Visualisierung: Absolute Zahlen
    plot_confusion_matrix(
        cm, 
        unique_authors, 
        normalize=False, 
        title="Konfusionsmatrix der Autorenklassifikation (absolute Zahlen)",
        output_file="confusion_matrix_absolute.png"
    )
    
    # Zweite Visualisierung: Normalisierte Werte
    plot_confusion_matrix(
        cm, 
        unique_authors, 
        normalize=True, 
        title="Konfusionsmatrix der Autorenklassifikation (normalisiert)",
        output_file="confusion_matrix_normalized.png"
    )
    
    # 5. Detaillierte Analyse erstellen
    logger.info("Erstelle detaillierten Analysebericht...")
    # Konfidenzwerte für jeden Vorhersagefall berechnen
    confidences = []
    for content in df['content']:
        _, _, confidence = predict_author(content, model, tokenizer, classes)
        confidences.append(confidence)
    
    create_author_analysis_report(
        df, 
        true_authors, 
        predicted_authors, 
        confidences, 
        output_dir='author_analysis_results'
    )
    
    logger.info("Analyse abgeschlossen.")

if __name__ == "__main__":
    main() 