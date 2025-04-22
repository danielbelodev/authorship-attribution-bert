import pandas as pd
import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader
from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    Trainer,
    TrainingArguments,
    DataCollatorWithPadding,
    EarlyStoppingCallback
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, confusion_matrix
import sqlalchemy
import seaborn as sns
import matplotlib.pyplot as plt
from collections import defaultdict

# Datenbankverbindung
engine = sqlalchemy.create_engine('mysql+mysqlconnector://root:1234@localhost/diplomarbeit')

# SQL-Abfrage
query = """
SELECT a.id as article_id, a.content, auth.name as author
FROM articles a
JOIN placeholder p ON a.id = p.article_id
JOIN authors auth ON p.author_id = auth.id
"""

# Daten laden
df = pd.read_sql(query, engine)
df = df[df['author'] != 'kein Autor']

# Nur Autoren mit mindestens 10 Artikeln
author_article_counts = df['author'].value_counts()
authors_with_min_10_articles = author_article_counts[author_article_counts >= 10].index
df_filtered = df[df['author'].isin(authors_with_min_10_articles)]

# Autor → Artikel-IDs
author_to_articles = defaultdict(set)
for _, row in df_filtered.iterrows():
    author_to_articles[row['author']].add(row['article_id'])

# Train/Test-Split pro Autor (80/20)
train_article_ids_by_author = {}
test_article_ids_by_author = {}

for author, article_ids in author_to_articles.items():
    article_ids_list = list(article_ids)
    train_ids, test_ids = train_test_split(article_ids_list, test_size=0.2, random_state=42)
    train_article_ids_by_author[author] = set(train_ids)
    test_article_ids_by_author[author] = set(test_ids)

    # Testartikel: wenn mindestens ein Autor den Artikel im Testset hat
test_article_ids = set()
for ids in test_article_ids_by_author.values():
    test_article_ids.update(ids)

all_article_ids = set(df_filtered['article_id'].unique())
train_article_ids = all_article_ids - test_article_ids

# Trainings-/Test-Daten
train_df = df_filtered[df_filtered['article_id'].isin(train_article_ids)].reset_index(drop=True)
test_df = df_filtered[df_filtered['article_id'].isin(test_article_ids)].reset_index(drop=True)

# Label-Encoding
label_encoder = LabelEncoder()
train_df['author_id'] = label_encoder.fit_transform(train_df['author'])
test_df['author_id'] = label_encoder.transform(test_df['author'])

# Dataset-Klasse
class TextDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts.iloc[idx],
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors="pt"
        )
        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'labels': torch.tensor(self.labels.iloc[idx], dtype=torch.long)
        }
    
# Tokenizer & Dataset
tokenizer = BertTokenizer.from_pretrained('bert-base-german-cased')
train_dataset = TextDataset(train_df['content'], train_df['author_id'], tokenizer)
test_dataset = TextDataset(test_df['content'], test_df['author_id'], tokenizer)
data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

# Modell
num_labels = len(label_encoder.classes_)
model = BertForSequenceClassification.from_pretrained('bert-base-german-cased', num_labels=num_labels)

# Compute Metrics
def compute_metrics(p):
    preds = np.argmax(p.predictions, axis=1) if isinstance(p.predictions, np.ndarray) else np.argmax(p.predictions[0], axis=1)
    return {"accuracy": accuracy_score(p.label_ids, preds)}

# TrainingArguments
training_args = TrainingArguments(
    output_dir='./author_classification2',
    num_train_epochs=3,
    learning_rate=5e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    evaluation_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
    metric_for_best_model='eval_loss',
    warmup_steps=500,
    lr_scheduler_type='linear',
    logging_dir='./logs',
    report_to="none",
    fp16=True  # falls du eine GPU mit FP16-Unterstützung hast
)

# Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    tokenizer=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
)

# Training starten
trainer.train()