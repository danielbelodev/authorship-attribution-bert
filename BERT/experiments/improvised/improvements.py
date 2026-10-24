import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    BertTokenizer, 
    BertForSequenceClassification, 
    Trainer, 
    TrainingArguments,
    EarlyStoppingCallback,
    get_linear_schedule_with_warmup
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
from sklearn.utils import resample
import numpy as np
import sqlalchemy
import re
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import seaborn as sns
import nltk
from nltk.tokenize import sent_tokenize
import os
import logging

# Einrichten des Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bert_training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set device for training
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"Using device: {device}")

# NLTK Download für Satzgrenzenerkennung
try:
    nltk.download('punkt', quiet=True)
except:
    logger.warning("NLTK Punkt Tokenizer konnte nicht heruntergeladen werden. Fallback auf einfache Satzgrenzen.")

# 1. Verbesserte Textvorverarbeitung
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

def tokenize_and_truncate(text, tokenizer, max_length=512):
    """Tokenisiert Text und versucht, sinnvolle Satzgrenzen für die Trunkierung zu finden."""
    try:
        sentences = sent_tokenize(text, language='german')
    except:
        # Fallback auf einfache Satzerkennung
        sentences = re.split(r'(?<=[.!?])\s+', text)
    
    tokens = []
    for sentence in sentences:
        sentence_tokens = tokenizer.tokenize(sentence)
        if len(tokens) + len(sentence_tokens) <= max_length - 2:  # -2 für [CLS] und [SEP]
            tokens.extend(sentence_tokens)
        else:
            break
    
    # Wenn keine kompletten Sätze passen, nutze Standard-Trunkierung
    if not tokens:
        tokens = tokenizer.tokenize(text)[:max_length - 2]
    
    return tokens

# 1. Verbindung zur Datenbank herstellen und Daten abrufen
try:
    engine = sqlalchemy.create_engine(os.getenv("DB_URL", "mysql+mysqlconnector://root@localhost/diplomarbeit"))
    query = """
    SELECT articles.content, COALESCE(authors.name, 'kein Autor') AS author
    FROM articles
    LEFT JOIN authors ON articles.author_id = authors.id
    """
    df = pd.read_sql(query, engine)
    logger.info(f"Daten erfolgreich aus der Datenbank geladen. Total: {len(df)} Artikel")
except Exception as e:
    logger.error(f"Fehler beim Datenbankabruf: {str(e)}")
    raise

# 2. Filterung: Nur Artikel mit bekanntem Autor verwenden
df = df[df['author'] != 'kein Autor']
logger.info(f"Artikel mit bekanntem Autor: {len(df)}")

# Textbereinigung anwenden
df['content'] = df['content'].apply(clean_text)

# Autoren zu Labeln umwandeln
label_encoder = LabelEncoder()
df['author_id'] = label_encoder.fit_transform(df['author'])

# Debugging: Anzahl der Artikel pro Autor prüfen
logger.info("Anzahl der Artikel pro Autor:")
author_counts = df['author'].value_counts()
logger.info(f"\n{author_counts}")

# Schritt 3: Verbesserte Behandlung von Klassen-Ungleichgewicht
# Identifikation der wenig vertretenen Autoren (weniger als N Artikel)
min_samples = 5
low_count_authors = author_counts[author_counts < min_samples].index

# DataFrame für das erweiterte Dataset vorbereiten
balanced_df = df.copy()

# Erweiterte Oversampling-Strategie für wenig vertretene Autoren
for author in low_count_authors:
    author_articles = df[df['author'] == author]
    target_samples = max(min_samples, 5)  # Mindestens 5 Samples pro Autor
    
    # Angepasstes Resampling basierend auf verfügbaren Artikeln
    if len(author_articles) > 0:
        # Resampling der Artikel mit Augmentation
        n_samples = min(target_samples, len(author_articles) * 5)  # Vermeidung von Übertraining
        author_articles_oversampled = resample(
            author_articles, 
            replace=True,     # Sampling mit Zurücklegen
            n_samples=n_samples,
            random_state=42
        )
        
        balanced_df = pd.concat([balanced_df, author_articles_oversampled], ignore_index=True)
        logger.info(f"Autor '{author}': {len(author_articles)} → {len(author_articles) + n_samples} Artikel")

# Debugging: Überprüfen, ob Oversampling erfolgreich war
logger.info(f"Artikel nach Balancing: {len(balanced_df)}")
logger.info(f"Überprüfe finale Klassenverteilung:")
balanced_counts = balanced_df['author'].value_counts()
logger.info(f"\n{balanced_counts.head(10)}")

# Berechne Klassengewichte für Loss-Funktion
class_counts = balanced_df['author_id'].value_counts().sort_index()
class_weights = compute_class_weight(
    'balanced',
    classes=np.unique(balanced_df['author_id']),
    y=balanced_df['author_id']
)
class_weights = torch.tensor(class_weights, dtype=torch.float)
logger.info(f"Berechnete Klassengewichte: {class_weights}")

# Train- und Testdaten aufteilen mit Stratifizierung
train_texts, test_texts, train_labels, test_labels = train_test_split(
    balanced_df['content'], 
    balanced_df['author_id'], 
    test_size=0.2, 
    stratify=balanced_df['author_id'],  # Stratified Sampling
    random_state=42
)

# 3. Verbesserte Dataset-Klasse mit besserer Tokenisierung
tokenizer = BertTokenizer.from_pretrained('bert-base-german-cased')

class ImprovedTextDataset(Dataset):
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
        
        # Intelligente Tokenisierung mit Satzgrenzen
        tokens = tokenize_and_truncate(text, self.tokenizer, self.max_length)
        token_str = self.tokenizer.convert_tokens_to_string(tokens)
        
        # Tokenisiere mit Padding und Attention Mask
        encoding = self.tokenizer(
            token_str,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors="pt"
        )
        
        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'labels': torch.tensor(label, dtype=torch.long)
        }

# Verbesserte Datasets erstellen
train_dataset = ImprovedTextDataset(train_texts, train_labels, tokenizer)
test_dataset = ImprovedTextDataset(test_texts, test_labels, tokenizer)

# 4. Modell mit gewichteter Verlustfunktion definieren
class BertForWeightedSequenceClassification(BertForSequenceClassification):
    def __init__(self, config, class_weights=None):
        super().__init__(config)
        self.class_weights = class_weights
        
    def forward(self, input_ids=None, attention_mask=None, token_type_ids=None, 
                position_ids=None, head_mask=None, inputs_embeds=None, labels=None, **kwargs):
        outputs = super().forward(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            position_ids=position_ids,
            head_mask=head_mask,
            inputs_embeds=inputs_embeds,
            labels=None,  # Überschreibe labels, um eigene Verlustberechnung zu machen
            **kwargs
        )
        
        logits = outputs.logits
        
        if labels is not None:
            if self.class_weights is not None and self.class_weights.device != labels.device:
                self.class_weights = self.class_weights.to(labels.device)
            
            loss_fct = torch.nn.CrossEntropyLoss(weight=self.class_weights)
            loss = loss_fct(logits.view(-1, self.config.num_labels), labels.view(-1))
            outputs.loss = loss
            
        return outputs

# Modell initalisieren
model = BertForWeightedSequenceClassification.from_pretrained(
    'bert-base-german-cased',
    num_labels=len(label_encoder.classes_),
    class_weights=class_weights
)

# Modell auf GPU verschieben
model = model.to(device)
logger.info(f"Modell für {len(label_encoder.classes_)} Klassen konfiguriert.")

# 5. Verbesserte Trainingsoptionen mit Gradientenakkumulation und LR-Scheduling
training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=10,                 # Mehr Epochen für bessere Konvergenz
    per_device_train_batch_size=4,       # Kleinere Batch-Größe für Speichereffizienz
    per_device_eval_batch_size=8,
    gradient_accumulation_steps=4,       # Akkumuliere Gradienten über 4 Batches (effektiv 16er Batch)
    learning_rate=2e-5,                  # Angepasste Learning Rate für BERT
    weight_decay=0.01,                   # L2 Regularisierung
    logging_dir='./logs',
    logging_steps=10,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,         # Bestes Modell speichern
    metric_for_best_model="eval_loss",
    greater_is_better=False,             # Für Loss ist niedriger besser
    save_total_limit=3,                  # Nur die besten 3 Modelle speichern
    fp16=torch.cuda.is_available(),      # Mixed Precision Training, wenn GPU verfügbar
    report_to="none",                    # Keine externen Reports
    lr_scheduler_type="linear",          # Linearer LR Scheduler
    warmup_ratio=0.1,                    # 10% der Schritte für Warmup
    no_cuda=not torch.cuda.is_available()  # GPU nutzen wenn verfügbar
)

# Early Stopping Callback hinzufügen
callbacks = [EarlyStoppingCallback(early_stopping_patience=3)]

# Angepasster Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    callbacks=callbacks,
    tokenizer=tokenizer,  # Tokenizer für Feature Extraction
)

# 6. Modell trainieren
logger.info("Start des Modelltrainings...")
train_result = trainer.train()
logger.info(f"Training abgeschlossen: {train_result}")

# 7. Modell und Label Encoder speichern
output_dir = './bert_author_model_german'
os.makedirs(output_dir, exist_ok=True)
model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)
np.save(f'{output_dir}/classes.npy', label_encoder.classes_)
logger.info(f"Modell und Tokenizer gespeichert in {output_dir}")

# 8. Erweiterte Modellauswertung
logger.info("Führe detaillierte Modellauswertung durch...")
eval_results = trainer.evaluate()
logger.info(f"Evaluationsergebnisse: {eval_results}")

# Vorhersagen für Test-Daten generieren
logger.info("Generiere Vorhersagen für Test-Daten...")
predictions = trainer.predict(test_dataset)
pred_labels = np.argmax(predictions.predictions, axis=1)
true_labels = test_labels.reset_index(drop=True).values

# Classification Report erstellen
logger.info("Erstelle detaillierten Klassifikationsbericht...")
class_names = [label_encoder.classes_[i] for i in range(len(label_encoder.classes_))]
report = classification_report(true_labels, pred_labels, target_names=class_names, digits=3)
logger.info(f"Klassifikationsbericht:\n{report}")

# Confusion Matrix erstellen und plotten
cm = confusion_matrix(true_labels, pred_labels)
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=class_names, yticklabels=class_names)
plt.xlabel('Vorhergesagt')
plt.ylabel('Tatsächlich')
plt.title('Confusion Matrix')
plt.tight_layout()
plt.savefig(f'{output_dir}/confusion_matrix.png')
logger.info(f"Confusion Matrix gespeichert unter {output_dir}/confusion_matrix.png")

# 9. Protokollieren der Hyperparameter und Ergebnisse
with open(f'{output_dir}/training_summary.txt', 'w') as f:
    f.write(f"Training Summary\n")
    f.write(f"===============\n\n")
    f.write(f"Anzahl Klassen (Autoren): {len(label_encoder.classes_)}\n")
    f.write(f"Training Samples: {len(train_dataset)}\n")
    f.write(f"Test Samples: {len(test_dataset)}\n")
    f.write(f"Hyperparameter:\n")
    for key, value in training_args.to_dict().items():
        f.write(f"  {key}: {value}\n")
    f.write(f"\nEvaluationsergebnisse:\n")
    for key, value in eval_results.items():
        f.write(f"  {key}: {value}\n")
    f.write(f"\nKlassifikationsbericht:\n{report}\n")

logger.info(f"Training Summary gespeichert unter {output_dir}/training_summary.txt")
logger.info("Modelltraining und Evaluierung abgeschlossen!")

# Optional: Beispiel für Vorhersage mit dem trainierten Modell
def predict_author(text, model, tokenizer, label_encoder_classes, device='cpu'):
    """Vorhersage des Autors für einen Text."""
    model.eval()
    # Text reinigen und tokenisieren
    cleaned_text = clean_text(text)
    inputs = tokenizer(cleaned_text, truncation=True, padding='max_length', max_length=512, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
        
    logits = outputs.logits
    probabilities = torch.nn.functional.softmax(logits, dim=1)
    predicted_class = torch.argmax(probabilities, dim=1).item()
    predicted_author = label_encoder_classes[predicted_class]
    
    return predicted_author, probabilities.cpu().numpy()[0]

# Beispiel-Vorhersage (auskommentiert)
# sample_text = "Ein Beispieltext für die Vorhersage."
# pred_author, probs = predict_author(sample_text, model, tokenizer, label_encoder.classes_, device)
# logger.info(f"Vorhergesagter Autor für Beispieltext: {pred_author}")

# Ende des Skripts
