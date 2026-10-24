# Transformer & BERT – Background notes

Personal study notes written while preparing the thesis.

## What are LSTM and Transformers?
### Transformer
The Transformer Neural Network Architecture was initially used to solve Neural Machine Translation.
Here is a picture:![grafik](https://github.com/user-attachments/assets/ef25aeea-97dd-4143-8afd-6c809adefc14)
The Transformer is
* faster, because words are getting parsed separately
* Deeply bidirectional (the context of words is better learned as they will learn the context on both direction
### LSTM
And before that, LSTM Networks were used to solve the same problem:
Here is the structure of this Network:![grafik](https://github.com/user-attachments/assets/cc1f21d4-80cb-416b-b875-3a9b38587178)
This Network is 
* slow, because they parsed the words sequentially and are generated sequentially. Due to this, this network consumes a lot of time to learn.
* Not truly Bidirectional
Even in this example: ![grafik](https://github.com/user-attachments/assets/7ac0f94a-b7c8-4a0f-8210-ba6e5bfc334d)
The direction of the network just reads from left to right and right to left while concatenate each words, meaning you will lose some of the context.
## Structure of Transformer
The structure on the left: ![grafik](https://github.com/user-attachments/assets/9ade715a-3742-4e0f-a7c2-f88d40a239b4)
is the Encoder and the structure on the right: ![grafik](https://github.com/user-attachments/assets/68d729e0-8a81-4bb4-95c4-db92ec3b9bd6) is the decoder
## How does this work?
The Encoder will take the words simultaneously and generates embedding for every word simultaneously. This Embeddings are vectors and contain the meanings of the word. the more similar the word is to each other, the closer the number
The Decoder will take the embeddings and the previously generated words of the french sentence (example) and uses that to generate the next word and it will generate the french translation one word at a time until the end.
The **Encoder** learns:
* What is English?
* What is Grammar?
* What is Context?
The **Decoder** learns:
* how does English words relate to French words?
As you can see, both of the structures learn Language different and you can separate each other:
If you stack **Decoder**, you will get the GPT transformer architecture
If you stack **Encoder**, you will get BERT (short for: Bidirectional Encoder Representation from Transformers)
## BERT
short for: Bidirectional Encoder Representation from Transformers, and you can use BERT to solve problems like:
* Neural Machine Translation
* Question Answering
* Sentiment Analysis
* Text summarization
* etc.
It needs to understand the Language to solve these problems and fine tune BERT to learn a specific task. The first part of BERT training is to pretrain the Model to let it understand the language and fine tune him.
### Pretraining (Unsupervised Models)
![grafik](https://github.com/user-attachments/assets/7fcae3d3-fa82-462f-9e34-5a8d74e4d657)

#### Masked Language Model
A random sentence is filled with random Masks and it will try to output these masks
#### Next Sentence Prediction
Takes two sentences and determine, if the second sentence follows the first sentence

## Further reading
Good video explanation: https://www.youtube.com/watch?v=xI0HHN5XKDo
