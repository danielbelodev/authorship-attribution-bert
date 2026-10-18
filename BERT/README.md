# BERT-basierte Autorenklassifikation

Dieses Projekt verwendet ein BERT-Modell (Bidirectional Encoder Representations from Transformers), um Autoren anhand ihrer Artikel zu identifizieren. Es nutzt einen deutschsprachigen BERT-Ansatz zur Textklassifikation.

## Funktionalitäten

- **Textklassifikation**: Identifizierung von Autoren anhand ihrer Schreibstile und -muster
- **Datenbalancierung**: Behandlung von Klassen-Ungleichgewichten durch Oversampling
- **Gewichtete Loss-Funktion**: Berücksichtigung ungleicher Klassenverteilungen
- **Batch-Verarbeitung**: Verarbeitung großer Textmengen und Aggregation der Ergebnisse
- **Detaillierte Auswertung**: Visualisierung der Vorhersagen und Konfidenzwerte

## Installation

1. Klonen Sie das Repository:
   ```
   git clone <repository-url>
   cd BERT
   ```

2. Erstellen Sie eine virtuelle Umgebung und installieren Sie die Abhängigkeiten:
   ```
   python -m venv env
   source env/bin/activate  # Unter Windows: env\Scripts\activate
   pip install -r requirements.txt
   ```

3. Stellen Sie sicher, dass Sie eine MySQL-Datenbank mit den erforderlichen Tabellen eingerichtet haben.

## Verwendung

### Training

Um das Modell zu trainieren, führen Sie `improvements.py` aus:

```bash
python improvements.py
```

Dieser Prozess umfasst:
- Laden der Daten aus der MySQL-Datenbank
- Vorverarbeitung und Balancierung der Daten
- Training eines BERT-Modells für die Autorenklassifikation
- Speichern des trainierten Modells

### Vorhersage

Um Vorhersagen mit dem trainierten Modell zu treffen, nutzen Sie `predict.py`:

```bash
python predict.py
```

Sie können auch die predict_author-Funktion für eigene Texte verwenden:

```python
from predict import predict_author

text = "Ihr zu analysierender Text..."
author, scores, confidence = predict_author(text)
print(f"Vorhergesagter Autor: {author} (Konfidenz: {confidence:.3f})")
```

### GPU-Beschleunigung

Das System verwendet automatisch CUDA, wenn verfügbar. Sie können die Verfügbarkeit mit `test.py` überprüfen:

```bash
python test.py
```

## Modellstruktur

- **Basismodell**: bert-base-german-cased
- **Anpassungen**: Gewichtete Loss-Funktion, Class-Balancing, Early Stopping
- **Tokenisierung**: Verbesserte Tokenisierung mit Beachtung von Satzgrenzen
- **Textvorverarbeitung**: Bereinigung von HTML, URLs und Sonderzeichen

## Erweiterungen und Verbesserungen

Die aktuelle Version enthält bereits viele Verbesserungen:

- **Text Preprocessing**: Bessere Textbereinigung und Tokenisierung
- **Klassengewichtung**: Berücksichtigung ungleicher Klassenverteilungen
- **Early Stopping**: Vermeidung von Überanpassung
- **Gradientenakkumulation**: Ermöglicht effektiv größere Batch-Größen
- **Visualisierung**: Detaillierte Auswertung und Visualisierung der Ergebnisse

## Fehlerbehebung

Probleme mit CUDA? Überprüfen Sie:
- PyTorch-Installation mit CUDA-Unterstützung
- Kompatibilität der CUDA-Version

Probleme mit der Datenbank? Überprüfen Sie:
- MySQL-Server läuft
- Benutzeranmeldedaten sind korrekt
- Datenbanktabellen sind vorhanden und korrekt aufgebaut
