# Hallo, hier ist mein Protokoll, damit ich dies net vergessse und für dich Leon, wenn ich mal keine Zeit habe und nicht erreichbar bin.
## 20.11.24
Der Shit hat irgendwie richtig viel an daten geholded <= kann sein, dass ich einfach nur retarded war. Ich wollte die Logs/Records vom Bert-Modell in Github raufpushen,
ging da net, da ein Lock-Datei dabei gehindert hat, den Commit zu führen.
Es stand in der Fehlermeldung etwas von das ein Commit bereits initiert wurde, aber naja. Hab mein .venv gelöscht, alles versucht zu importen, dann ging da nix, da manche Libraries einfach nur
faxen gemacht haben wie accelarator (dieser Hurensohn) und am Ende des Tages bekam ich nur noch Fehler wegen CUDA
## 21.11.24
Hab im ReadMe.md versucht eine zusammenfassung zu verfassen über ein Video, welches BERT erklärt, hab dies aber nach dreiundeinhalb Minuten aufgegeben, da dieses Video besser anzuschauen ist => sitenote: ist emphelenswert, da wir auch in der Diplomarbeit genauer eingehen können,
wie Bert funktioniert, aus welchen Teil des Transformers der besteht und was davor verwendet wurde, bsp. LSMN oder so
als gelesen (zumindest von mir verfasst) zu werden. Hab ein neues conda-environment erstellt. Falls man dies reproduzieren will, bitte davor conda in die Systemumgebungsvariablen im **Path** hinzufügen
Hier sind die folgenden Befehle, die ich verwendet habe: 
```
conda install -c conda-forge pandas scikit-learn sqlalchemy mysql-connector-python -y
conda install pytorch torchvision torchaudio -c pytorch
pip install transformers
pip install sympy==1.13.1
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia
pip install accelerate>=0.26.0

```
Da funktioniert alles wieder und ich kann den Code ausführen.
Die derzeitige operation dauert: **7:30h** an mit einer Iterationsrate von: **207348**, muss dies aber verringern, da ich definitiv nicht 
genügend Speicher haben werde, diesen Shit komplett auszuführen. (Note: der Shit frisst mir gefühlt 1gb/min und mit meinen mageren: 220GB übrig, kann dies sehr schwierig werden
ok, ich muss definitiv abbrechen, kann dies nicht afforden. (Comparison: der result-ordner hat bereits 22GB für 8000 Iterationen gefressen)
Hell nah
Aber hey, es kann meine Grafikkarte erkennen (RTX 4070 Super)
Stand: 17:50, hab den Shit abgebrochen 
werd bei meinen PC keine games deinstallieren, da ich interesse habe, die noch zu spielen, aber eine andere Solution ist es, einfach ne externe Festplatten zu verwenden
Laut meinen berechnungen bräuchte ich, wenn ich kein Change machen im Code führe, ungefähr 530GB an Speicher, aber keine Sorge, ich werde dies Zahl leicht runterdrehen :)
