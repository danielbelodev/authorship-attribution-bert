import os
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import numpy as np
import sqlalchemy
from sklearn.utils import resample

# 1. Verbindung zur Datenbank herstellen und Daten abrufen
engine = sqlalchemy.create_engine(os.getenv("DB_URL", "mysql+mysqlconnector://root@localhost/diplomarbeit"))
query = """
SELECT articles.content, COALESCE(authors.name, 'kein Autor') AS author
FROM articles
LEFT JOIN authors ON articles.author_id = authors.id
"""

df = pd.read_sql(query, engine)

# 2. Filterung: Nur Artikel mit bekanntem Autor verwenden
df = df[df['author'] != 'kein Autor']

# Autoren zu Labeln umwandeln
label_encoder = LabelEncoder()
df['author_id'] = label_encoder.fit_transform(df['author'])

# Debugging: Anzahl der Artikel pro Autor prüfen
print("Anzahl der Artikel pro Autor:")
print(df['author'].value_counts())

# Schritt 3: Oversampling der weniger vertretenen Autoren
# Identifikation der wenig vertretenen Autoren (Autoren mit nur einem Artikel)
author_counts = df['author'].value_counts()
low_count_authors = author_counts[author_counts == 1].index

# Leeres DataFrame für das Oversampling vorbereiten
oversampled_df = df.copy()

# Artikel von wenig vertretenen Autoren mehrfach hinzufügen (z. B. 10-faches Oversampling)
for author in low_count_authors:
    author_articles = df[df['author'] == author]
    # Resampling der Artikel
    author_articles_oversampled = resample(author_articles, 
                                           replace=True,     # Sampling mit Zurücklegen
                                           n_samples=5,      # 5-fache Wiederholung
                                           random_state=42)  # Für Reproduzierbarkeit
    oversampled_df = pd.concat([oversampled_df, author_articles_oversampled], ignore_index=True)

# Debugging: Überprüfen, ob Oversampling erfolgreich war
print("Anzahl der Artikel nach Oversampling:")
print(oversampled_df['author'].value_counts())

# Train- und Testdaten aufteilen (jetzt mit oversampled_df)
train_texts, test_texts, train_labels, test_labels = train_test_split(
    oversampled_df['content'], 
    oversampled_df['author_id'], 
    test_size=0.2, 
    stratify=oversampled_df['author_id'],  # Stratified Sampling
    random_state=42
)

# 3. Tokenizer und Dataset erstellen (Deutschsprachiger Tokenizer)
tokenizer = BertTokenizer.from_pretrained('bert-base-german-cased')

class TextDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts.reset_index(drop=True)
        self.labels = labels.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        encoding = self.tokenizer(
            text, truncation=True, padding='max_length', max_length=self.max_length, return_tensors="pt"
        )
        return {
            'input_ids': encoding['input_ids'].squeeze(0),  # Entferne unnötige Dimensionen
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'labels': torch.tensor(label, dtype=torch.long)
        }

train_dataset = TextDataset(train_texts, train_labels, tokenizer)
test_dataset = TextDataset(test_texts, test_labels, tokenizer)

# 4. Modell laden und konfigurieren (Deutschsprachiges Modell)
model = BertForSequenceClassification.from_pretrained('bert-base-german-cased', num_labels=len(label_encoder.classes_))

# Debugging: Prüfen, ob die Modellkonfiguration korrekt ist
print(f"Modell für {len(label_encoder.classes_)} Klassen konfiguriert.")

# 5. TrainingArguments und Trainer initialisieren
training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=5,  # Erhöhe die Epochenanzahl
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    warmup_steps=100,
    weight_decay=0.01,
    logging_dir='./logs',
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,  # Bestes Modell speichern
    logging_steps=10,
    metric_for_best_model="eval_loss",
    save_total_limit=3
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset
)

# 6. Modell trainieren
trainer.train()

# 7. Modell und Label Encoder speichern
model.save_pretrained('./bert_author_model_german')
tokenizer.save_pretrained('./bert_author_model_german')
np.save('./bert_author_model_german/classes.npy', label_encoder.classes_)

# 8. Debugging: Auswertung durchführen
eval_results = trainer.evaluate()
print("Evaluationsergebnisse:", eval_results)
