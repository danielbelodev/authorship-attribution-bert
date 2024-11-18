import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import os
import sqlalchemy

# 1. Datenbankverbindung und Datenimport
# Verwenden einer expliziten Verbindung
engine = sqlalchemy.create_engine('mysql+mysqlconnector://root:1234@localhost/diplomarbeit')

# Explizite Verbindung herstellen
with engine.connect() as connection:
    query = """
    SELECT articles.content, authors.name AS author
    FROM articles
    JOIN authors ON articles.author_id = authors.id 
    """
    # Abfrage mit der Verbindung durchführen
    df = pd.read_sql(query, con=connection)

# 2. Daten vorverarbeiten
# Autoren in numerische Labels umwandeln
label_encoder = LabelEncoder()
df['author_id'] = label_encoder.fit_transform(df['author'])

# Train- und Testdaten aufteilen
train_texts, test_texts, train_labels, test_labels = train_test_split(df['content'], df['author_id'], test_size=0.2)

# 3. Tokenizer und Dataset erstellen
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

# Custom Dataset für die PyTorch DataLoader
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

# Erstellen der Trainings- und Test-Datensätze
train_dataset = TextDataset(train_texts, train_labels, tokenizer)
test_dataset = TextDataset(test_texts, test_labels, tokenizer)

# GPU-Prüfung und Gerätezuteilung
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# 4. Modell laden und konfigurieren
model = BertForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=len(label_encoder.classes_))
model.to(device)  # Modell auf GPU verschieben, falls verfügbar

# 5. TrainingArguments und Trainer initialisieren
training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=3,
    per_device_train_batch_size=16,  # Erhöhte Batchgröße
    per_device_eval_batch_size=16,
    warmup_steps=500,
    weight_decay=0.01,
    logging_dir='./logs',
    evaluation_strategy="epoch",
    fp16=True  # Mixed Precision Training aktivieren
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset
)

# 6. Modell trainieren
trainer.train()

# Modell und Label Encoder speichern
model.save_pretrained('./bert_author_model')
tokenizer.save_pretrained('./bert_author_model')
label_encoder.classes_.tofile('./bert_author_model/classes.npy')
