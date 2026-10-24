# Tracing Linguistic Fingerprints: AI-Based Authorship Attribution

Diplomarbeit an der HTL Hallein (Wirtschaftsingenieure – Betriebsinformatik), 2024/25, bewertet mit **Sehr gut**.

Kann ein Sprachmodell erkennen, **wer** einen Zeitungsartikel geschrieben hat, nur anhand des Schreibstils?
Dafür haben wir rund 200.000 Artikel von [derStandard.at](https://www.derstandard.at) gesammelt und ein deutsches BERT-Modell darauf trainiert, die Autorin oder den Autor eines Textes vorherzusagen.

## Team

Daniel Belogrivov  
Leon Weber

## Pipeline

```
derStandard-Sitemaps ──► Crawler (requests + BeautifulSoup)
                              │
                              ▼
                         CSV-Export ──► MySQL (articles, authors, n:m-Zuordnung)
                                              │
              Apache Airflow: täglicher Lauf  │
              (crawlen + in DB laden)         ▼
                                     BERT-Fine-Tuning (bert-base-german-cased)
                                              │
                                              ▼
                                Auswertung: Accuracy gesamt / pro Autor,
                                Confusion Matrix, Accuracy vs. Artikelanzahl
```

## Ergebnisse

| | |
|---|---|
| Modell | `bert-base-german-cased`, Fine-Tuning für Sequence Classification |
| Daten | ~212.000 Artikel-Autor-Paare, nur Autor:innen mit ≥ 10 Artikeln |
| Split | 80/20 pro Autor, auf Artikelebene (kein Artikel in Train **und** Test) |
| Training | 3 Epochen, LR 5e-5, Batch 8, FP16 auf GPU, ca. 5,5 h |
| **Test-Accuracy** | **65,1 %** (Epoche 1: 53,0 % → Epoche 2: 61,3 % → Epoche 3: 65,1 %) |

Die wichtigste Erkenntnis: **Je mehr Artikel es von einer Person gibt, desto besser wird sie erkannt.** Ab etwa 1.000 Artikeln liegt die Accuracy pro Autor:in meistens bei 85–95 %, bei wenigen Artikeln schwankt sie stark.

![Accuracy vs. Artikelanzahl](BERT/final_results/accuracy_vs_article_count.png)

> **Hinweis zu den Zahlen:** Artikel auf derStandard enden oft mit einer Signatur wie „(Name, 21.8.2024)". Beim ursprünglichen Training war diese Signatur noch im Text, das Modell konnte den Namen also teilweise direkt ablesen. Die aktuelle Version von `BERT/data_utils.py` entfernt die Signatur. Die Grafiken in `BERT/final_results/` stammen noch aus dem alten Auswertungsskript, das über alle Artikel (inkl. Trainingsdaten) gerechnet hat. Mit `BERT/evaluate.py` werden sie jetzt nur auf dem Testset neu erzeugt.

## Tech-Stack

- **Python** (pandas, NumPy, scikit-learn)
- **PyTorch** + **Hugging Face Transformers** (BERT, `Trainer`, Early Stopping, Mixed Precision)
- **Web Scraping:** requests, BeautifulSoup, lxml (XML-Sitemaps)
- **Datenbank:** MySQL, SQLAlchemy (ORM, n:m-Beziehung Artikel ↔ Autoren)
- **Orchestrierung:** Apache Airflow (tägliche DAGs für Crawling und DB-Import)
- **Visualisierung:** Matplotlib, Seaborn

## Projektstruktur

```
├── crawler/              Crawler für derStandard (komplettes Archiv / nur heutige Artikel)
├── database/
│   ├── schema.sql        MySQL-Schema
│   └── connection.py     CSV → MySQL Import
├── db.py                 Import mit SQLAlchemy-ORM und Autoren-Erkennung ("A und B", "X aus Wien", …)
├── airflow/
│   ├── dags/             Airflow-DAGs (Crawling + Import, täglich)
│   └── legacy_dags/      ältere DAG-Versionen
├── BERT/
│   ├── data_utils.py     Daten laden, Signatur entfernen, Train/Test-Split
│   ├── train.py          Fine-Tuning des Modells
│   ├── evaluate.py       Auswertung auf dem Testset + Grafiken
│   ├── final_results/    Grafiken für die Diplomarbeit
│   ├── notebooks/        Original-Notebooks mit Trainings-Output
│   └── experiments/      frühere Versuche (Class Weights, Oversampling, Chunk-Vorhersage)
└── docs/                 Notizen zu Transformer/BERT
```

## Selbst ausführen

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# MySQL-Datenbank anlegen
mysql -u root -p < database/schema.sql

# Zugangsdaten setzen (siehe .env.example)
export DB_URL="mysql+mysqlconnector://root:PASSWORT@localhost:3306/diplomarbeit"

# 1. Artikel crawlen und importieren
python crawler/DerStandard_crawler.py
python db.py

# 2. Modell trainieren und auswerten (GPU empfohlen)
cd BERT
python train.py
python evaluate.py
```

Die gecrawlten Artikel und das trainierte Modell sind nicht im Repo (Urheberrecht bzw. Dateigröße).

## Mögliche Erweiterungen

- Längere Artikel in mehrere 512-Token-Abschnitte teilen statt abzuschneiden (Ansatz in `BERT/experiments/improvised/predict.py`)
- Neu trainieren ohne Signatur und Ergebnisse vergleichen
- Vergleich mit klassischer Stilometrie (z. B. Character-n-Grams + Logistic Regression) als Baseline
