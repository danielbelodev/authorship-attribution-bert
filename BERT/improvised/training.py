import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import numpy as np
import sqlalchemy

# 1. Verbindung zur Datenbank herstellen und Daten abrufen
engine = sqlalchemy.create_engine('mysql+mysqlconnector://root:1234@localhost/diplomarbeit')
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

# Train- und Testdaten aufteilen
train_texts, test_texts, train_labels, test_labels = train_test_split(df['content'], df['author_id'], test_size=0.2, random_state=42)

# 3. Tokenizer und Dataset erstellen (Deutschsprachiger Tokenizer)
tokenizer = BertTokenizer.from_pretrained('bert-base-german-cased')

class TextDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts.iloc[idx]
        label = self.labels.iloc[idx]
        encoding = self.tokenizer(text, truncation=True, padding='max_length', max_length=self.max_length, return_tensors="pt")
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

train_dataset = TextDataset(train_texts, train_labels, tokenizer)
test_dataset = TextDataset(test_texts, test_labels, tokenizer)

# 4. Modell laden und konfigurieren (Deutschsprachiges Modell)
model = BertForSequenceClassification.from_pretrained('bert-base-german-cased', num_labels=len(label_encoder.classes_))

# 5. TrainingArguments und Trainer initialisieren
training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=3,  # Passe die Anzahl der Epochen an
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    warmup_steps=500,
    weight_decay=0.01,
    logging_dir='./logs', 
    evaluation_strategy="epoch",
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
