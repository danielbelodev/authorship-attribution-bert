import torch
from transformers import BertTokenizer, BertForSequenceClassification
import numpy as np
from scipy.stats import entropy
import re
from bs4 import BeautifulSoup
import logging
import os
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# Einrichten des Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bert_prediction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Gerät für Inferenz festlegen
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"Using device: {device}")

# Verbesserte Textvorverarbeitung
def clean_text(text):
    """Bereinigt Text von HTML-Tags, URLs und Sonderzeichen."""
    if not isinstance(text, str):
        return ""
    # HTML-Tags entfernen
    try:
        text = BeautifulSoup(text, "html.parser").get_text()
    except:
        pass
    # URLs entfernen
    text = re.sub(r'http\S+', '', text)
    # Mehrfache Leerzeichen entfernen
    text = re.sub(r'\s+', ' ', text)
    # Unnötige Sonderzeichen entfernen aber deutsche Umlaute behalten
    text = re.sub(r'[^\w\s\äöüÄÖÜß.,!?]', '', text)
    return text.strip()

# Modell, Tokenizer und Klassen laden
def load_model(model_path='./bert_author_model_german'):
    """Lädt das trainierte Modell, den Tokenizer und die Klassen."""
    logger.info(f"Lade Modell aus {model_path}")
    
    if not os.path.exists(model_path):
        logger.error(f"Modellpfad existiert nicht: {model_path}")
        raise FileNotFoundError(f"Modellpfad existiert nicht: {model_path}")
    
    try:
        model = BertForSequenceClassification.from_pretrained(model_path)
        model = model.to(device)
        model.eval()
        
        tokenizer = BertTokenizer.from_pretrained(model_path)
        classes = np.load(f'{model_path}/classes.npy', allow_pickle=True)
        
        logger.info(f"Modell erfolgreich geladen für {len(classes)} Klassen")
        return model, tokenizer, classes
    except Exception as e:
        logger.error(f"Fehler beim Laden des Modells: {str(e)}")
        raise

# Hauptfunktion: Text in Abschnitte aufteilen
def split_text(text, tokenizer, max_length=512):
    """Teilt einen langen Text in überlappende Abschnitte auf."""
    # Text bereinigen
    text = clean_text(text)
    
    # Tokenisieren
    all_tokens = tokenizer.tokenize(text)
    
    # Wenn Text kürzer als max_length ist, gib ihn direkt zurück
    if len(all_tokens) <= max_length - 2:  # -2 für [CLS] und [SEP]
        return [tokenizer.convert_tokens_to_string(all_tokens)]
    
    # Überlappung von 20%
    stride = int(max_length * 0.8)
    chunks = []
    
    # Text in überlappende Abschnitte aufteilen
    for i in range(0, len(all_tokens), stride):
        chunk_tokens = all_tokens[i:i + max_length - 2]  # -2 für [CLS] und [SEP]
        if len(chunk_tokens) >= 50:  # Mindestens 50 Token pro Chunk
            chunk_text = tokenizer.convert_tokens_to_string(chunk_tokens)
            chunks.append(chunk_text)
    
    # Sicherstellen, dass mindestens ein Chunk zurückgegeben wird
    if not chunks and all_tokens:
        chunks = [tokenizer.convert_tokens_to_string(all_tokens[:max_length - 2])]
    
    return chunks

# Verbesserte Vorhersagefunktion
def predict_author(text, model=None, tokenizer=None, classes=None, threshold=0.6, min_confidence=0.2):
    """
    Sagt den Autor eines Textes vorher und gibt Konfidenzwerte zurück.
    
    Args:
        text: Der zu analysierende Text
        model, tokenizer, classes: Optional, wenn nicht angegeben, werden sie geladen
        threshold: Schwellenwert für die Entropie-Warnung
        min_confidence: Minimale Konfidenz für eine gültige Vorhersage
    
    Returns:
        tuple: (Vorhergesagter Autor, Dictionary mit Ähnlichkeitsscores, Konfidenz)
    """
    # Falls nicht übergeben, lade Modell, Tokenizer und Klassen
    if model is None or tokenizer is None or classes is None:
        model, tokenizer, classes = load_model()
    
    # Sicherstellen, dass das Modell im Evaluierungsmodus ist
    model.eval()
    
    # Zähle Token 
    total_tokens = 0
    aggregated_probs = None
    
    # Text in Abschnitte aufteilen und für jeden Abschnitt Vorhersagen treffen
    chunks = split_text(text, tokenizer)
    logger.info(f"Text in {len(chunks)} Abschnitte aufgeteilt")
    
    # Vorhersagen für jeden Abschnitt
    for chunk in tqdm(chunks, desc="Verarbeite Textabschnitte"):
        # Tokenisierung mit Padding und Attention Mask
        inputs = tokenizer(
            chunk, 
            return_tensors="pt", 
            truncation=True, 
            padding='max_length', 
            max_length=512
        )
        
        # Auf GPU verschieben, falls verfügbar
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Token zählen (abzüglich Padding)
        token_count = inputs['attention_mask'].sum().item()
        
        # Vorhersage durchführen
        with torch.no_grad():
            outputs = model(**inputs)
        
        # Logits zu Wahrscheinlichkeiten umwandeln
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        # Ergebnisse aggregieren (gewichtet nach Token-Anzahl)
        if aggregated_probs is None:
            aggregated_probs = probabilities.squeeze() * token_count
        else:
            aggregated_probs += probabilities.squeeze() * token_count
        
        total_tokens += token_count
    
    # Normalisieren der aggregierten Wahrscheinlichkeiten
    if total_tokens > 0:
        aggregated_probs /= total_tokens
    
    # Zu Numpy umwandeln
    probs_np = aggregated_probs.cpu().numpy()
    
    # Autor mit höchster Wahrscheinlichkeit auswählen
    predicted_class = probs_np.argmax()
    predicted_author = classes[predicted_class]
    confidence = probs_np[predicted_class]
    
    # Dictionary mit allen Ähnlichkeitsscores erstellen
    similarity_scores = {classes[i]: float(prob) for i, prob in enumerate(probs_np)}
    
    # Entropie der Verteilung prüfen
    distribution_entropy = entropy(probs_np)
    max_entropy = np.log(len(classes))
    normalized_entropy = distribution_entropy / max_entropy
    
    # Warnung, wenn Verteilung zu gleichmäßig ist (Entropie zu hoch)
    if normalized_entropy > threshold:
        logger.warning(
            f"Vorhersage möglicherweise unzuverlässig. "
            f"Normalisierte Entropie: {normalized_entropy:.3f}, "
            f"Höchste Konfidenz: {confidence:.3f}"
        )
    
    # Wenn die Konfidenz zu niedrig ist, Warnung ausgeben
    if confidence < min_confidence:
        logger.warning(f"Niedrige Konfidenz: {confidence:.3f} < {min_confidence}")
    
    return predicted_author, similarity_scores, confidence

# Visualisierungsfunktion für die Top-N-Autoren
def visualize_predictions(similarity_scores, n=5, title="Top-Autoren nach Wahrscheinlichkeit"):
    """Visualisiert die Top-N-Autoren nach Wahrscheinlichkeit als Balkendiagramm."""
    # Top-N-Autoren auswählen
    top_n = dict(sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)[:n])
    
    # Balkendiagramm erstellen
    plt.figure(figsize=(10, 6))
    bars = plt.bar(top_n.keys(), top_n.values(), color='skyblue')
    plt.xlabel('Autor')
    plt.ylabel('Wahrscheinlichkeit')
    plt.title(title)
    plt.xticks(rotation=45, ha='right')
    
    # Werte über den Balken anzeigen
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width()/2.,
            height + 0.01,
            f'{height:.3f}',
            ha='center', 
            va='bottom'
        )
    
    plt.tight_layout()
    return plt.gcf()

# Hauptfunktion für Batch-Vorhersagen
def batch_predict(texts, output_file=None, plot=True):
    """Führt Batch-Vorhersagen für mehrere Texte durch."""
    # Modell, Tokenizer und Klassen laden
    model, tokenizer, classes = load_model()
    
    results = []
    
    # Für jeden Text Vorhersagen treffen
    for i, text in enumerate(texts):
        logger.info(f"Verarbeite Text {i+1}/{len(texts)} (Länge: {len(text)} Zeichen)")
        
        # Vorhersage
        predicted_author, similarities, confidence = predict_author(
            text, model, tokenizer, classes
        )
        
        # Ergebnisse speichern
        result = {
            "text_id": i + 1,
            "text_preview": text[:100] + "..." if len(text) > 100 else text,
            "predicted_author": predicted_author,
            "confidence": confidence,
            "top_5_authors": dict(sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:5])
        }
        results.append(result)
        
        # Ergebnisse ausgeben
        logger.info(f"Text {i+1}: Vorhergesagter Autor: {predicted_author} (Konfidenz: {confidence:.3f})")
        
        # Visualisieren, falls gewünscht
        if plot:
            fig = visualize_predictions(
                similarities,
                title=f"Text {i+1}: Top-Autoren nach Wahrscheinlichkeit"
            )
            plt.savefig(f"prediction_result_{i+1}.png")
            plt.close(fig)
            logger.info(f"Visualisierung gespeichert als prediction_result_{i+1}.png")
    
    # Ergebnisse in Datei speichern, falls gewünscht
    if output_file:
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"Ergebnisse gespeichert in {output_file}")
    
    return results

# Wenn direkt ausgeführt, führe Beispiel-Vorhersagen durch
if __name__ == "__main__":
    example_texts = [
        "Es gibt kaum ein anderes Thema, das derart polarisiert: Wer am Wirtshaustisch ordentlich streiten will, muss nur über die Maskenpflicht oder die Corona-Impfung sprechen.",
        "Künstliche Intelligenz wird immer relevanter in der heutigen Gesellschaft und bietet neue Möglichkeiten, komplexe Probleme zu lösen. Die Forschung auf diesem Gebiet schreitet rasch voran.",
        "Die Philosophie der Antike hatte einen großen Einfluss auf die westliche Zivilisation. Denker wie Platon und Aristoteles prägten das Denken über Jahrhunderte hinweg mit ihren revolutionären Ideen."
    ]
    
    # Batch-Vorhersagen durchführen
    results = batch_predict(example_texts, output_file="prediction_results.json")
    
    # Detaillierte Ergebnisse anzeigen
    for i, result in enumerate(results):
        print(f"\nText {i+1}: {result['text_preview']}")
        print(f"Vorhergesagter Autor: {result['predicted_author']} (Konfidenz: {result['confidence']:.3f})")
        print("Top-5 Autoren:")
        for author, score in result['top_5_authors'].items():
            print(f"  {author}: {score:.3f}")
