import torch

if torch.cuda.is_available():
    print(f"CUDA verfügbar: {torch.cuda.get_device_name(0)}")
else:
    print("CUDA ist nicht verfügbar, es wird die CPU verwendet.")
