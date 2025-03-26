import torch
from transformers import BertTokenizer, BertForSequenceClassification
import numpy as np
from scipy.stats import entropy

# Geladene Klassen (Autoren) und das Modell
import os

# Aktuelles Verzeichnis ermitteln und Pfad konstruieren
current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, 'bert_author_model_german')

model = BertForSequenceClassification.from_pretrained(model_path)
tokenizer = BertTokenizer.from_pretrained(model_path)
model = BertForSequenceClassification.from_pretrained(model_path)
tokenizer = BertTokenizer.from_pretrained(model_path)
classes = np.load(f'{model_path}/classes.npy', allow_pickle=True)

def split_text(text, max_length=512):
    tokens = tokenizer.tokenize(text)
    for i in range(0, len(tokens), max_length):
        yield tokenizer.convert_tokens_to_string(tokens[i:i + max_length])

def predict_author(text):
    model.eval()
    total_tokens = 0
    probabilities_total = torch.zeros(len(classes))

    for chunk in split_text(text):
        inputs = tokenizer(chunk, return_tensors="pt", truncation=True, padding='max_length', max_length=512)
        token_count = inputs['input_ids'].size(1)
        with torch.no_grad():
            outputs = model(**inputs)
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
        probabilities_total += probabilities.squeeze() * token_count
        total_tokens += token_count

    probabilities_total /= total_tokens
    probabilities_total = probabilities_total.numpy()
    predicted_class = probabilities_total.argmax()
    predicted_author = classes[predicted_class]
    similarity_scores = {classes[i]: prob for i, prob in enumerate(probabilities_total)}

    # Entropie prüfen
    distribution_entropy = entropy(probabilities_total)
    max_entropy = np.log(len(classes))
    if distribution_entropy > 0.9 * max_entropy:
        print("Warnung: Vorhersagen sind möglicherweise nicht aussagekräftig. Überprüfe das Modell.")

    return predicted_author, similarity_scores

texts = [
    "Es gibt kaum ein anderes Thema, das derart polarisiert: Wer am Wirtshaustisch ordentlich streiten will",
    "Künstliche Intelligenz wird immer relevanter in der heutigen Gesellschaft und bietet neue Möglichkeiten",
    "Die Philosophie der Antike hatte einen großen Einfluss auf die westliche Zivilisation"
]

for text in texts:
    predicted_author, similarities = predict_author(text)
    print(f"Text: {text[:50]}...")
    print(f"Vorhergesagter Autor: {predicted_author}")
    print("Top-5 Ähnlichkeitsscores:")
    for author, score in sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"{author}: {score:.2f}")
    print("-" * 50)
