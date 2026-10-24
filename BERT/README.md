# BERT-basierte Autorenklassifikation

Dieses Projekt verwendet ein BERT-Modell (Bidirectional Encoder Representations from Transformers), um Autoren anhand ihrer Artikel zu identifizieren. Es nutzt einen deutschsprachigen BERT-Ansatz zur Textklassifikation.

## Funktionalitäten

- **Textklassifikation**: Identifizierung von Autoren anhand ihrer Schreibstile und -muster
- **Sauberer Train/Test-Split**: pro Autor, auf Artikelebene, ohne Signatur im Text
- **Auswertung**: Accuracy gesamt und pro Autor, normierte Confusion Matrix, Accuracy vs. Artikelanzahl

## Installation

1. Klonen Sie das Repository:
   ```
   git clone https://github.com/danielbelodev/diplomarbeit.git
   cd diplomarbeit
   ```

2. Erstellen Sie eine virtuelle Umgebung und installieren Sie die Abhängigkeiten:
   ```
   python -m venv env
   source env/bin/activate  # Unter Windows: env\Scripts\activate
   pip install -r requirements.txt
   ```

3. MySQL-Datenbank mit `database/schema.sql` anlegen und `DB_URL` setzen (siehe `.env.example`).

## Verwendung

```bash
python train.py      # Fine-Tuning, speichert das beste Modell in ./author_classification2/best
python evaluate.py   # Auswertung NUR auf dem Testset, erzeugt die Grafiken
```

`data_utils.py` enthält die gemeinsame Datenaufbereitung, damit Training und Auswertung exakt denselben Split und dieselbe Autoren-Zuordnung verwenden:
- nur Autor:innen mit mindestens 10 Artikeln
- Autorensignatur „(Name, Datum)" am Artikelende wird entfernt
- 80/20-Split pro Autor auf Artikelebene

Den Checkpoint für `evaluate.py` kann man mit `CHECKPOINT_PATH=... python evaluate.py` setzen.

Frühere Versuche (Class Weights, Oversampling, Vorhersage über mehrere Text-Chunks) liegen in `experiments/`. Die Original-Notebooks mit dem kompletten Trainings-Output in `notebooks/`.

## Modellstruktur

- **Basismodell**: bert-base-german-cased
- **Finale Version (`train.py`)**: Standard-Cross-Entropy, Early Stopping, Mixed Precision, max. 512 Token
- **Experimente**: gewichtete Loss-Funktion, Oversampling, Tokenisierung an Satzgrenzen

## Fehlerbehebung

Probleme mit CUDA? Überprüfen Sie:
- PyTorch-Installation mit CUDA-Unterstützung
- Kompatibilität der CUDA-Version
- Test: `python experiments/original/test.py`

Probleme mit der Datenbank? Überprüfen Sie:
- MySQL-Server läuft
- Benutzeranmeldedaten sind korrekt
- Datenbanktabellen sind vorhanden und korrekt aufgebaut
