import torch
from transformers import BertTokenizer, BertForSequenceClassification
import numpy as np
import pandas as pd

# Geladene Klassen (Autoren) und das Modell
model_path = './bert_author_model'
model = BertForSequenceClassification.from_pretrained(model_path)
tokenizer = BertTokenizer.from_pretrained(model_path)
classes = np.fromfile(f'{model_path}/classes.npy', dtype='<U255')

# Funktion zur Vorhersage
def predict_author(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding='max_length', max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    predicted_class = probabilities.argmax().item()
    return classes[predicted_class]

# Beispiel: Einen neuen Text analysieren
new_text = "Hier kommt ein Beispieltext, der einem Autor zugeordnet werden soll."
predicted_author = predict_author(new_text)
print(f"Der vorhergesagte Autor ist: {predicted_author}")
