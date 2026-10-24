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
from sklearn.metrics import accuracy_score

from data_utils import load_articles, split_by_author

# Daten laden (ohne Autorensignatur) und pro Autor 80/20 aufteilen
df_filtered = load_articles()
train_df, test_df, label_encoder = split_by_author(df_filtered)

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
    eval_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
    metric_for_best_model='eval_loss',
    warmup_steps=500,
    lr_scheduler_type='linear',
    logging_dir='./logs',
    report_to="none",
    fp16=torch.cuda.is_available()  # Mixed Precision nur mit GPU
)

# Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    processing_class=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
)

# Training starten
trainer.train()

# Bestes Modell + Klassen speichern, damit evaluate.py dieselbe Zuordnung nutzt
output_dir = './author_classification2/best'
trainer.save_model(output_dir)
np.save(f'{output_dir}/classes.npy', label_encoder.classes_)
