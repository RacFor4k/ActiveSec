# 🤖 CryptoAI: блок искусственного интеллекта

![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Status](https://img.shields.io/badge/status-prototype-orange)

## 🧩 Общая идея проекта

CryptoAI — это один из модулей большого проекта, предназначенный для обучения нейросети различать бинарные данные: **зашифрованные** или **незашифрованные**.

## 🧠 Архитектура нейросети

### ✏️ Компоненты

- Embedding: каждый байт превращается в вектор признаков.
- CNN блок: две Conv1d + MaxPooling + BatchNorm + Dropout.
- AttentionPool: агрегация признаков с обучаемым вниманием.
- LearnedPositionalEncoding: позиционная информация.
- Transformer encoder: поиск глобальных зависимостей.
- MLP decoder: финальная классификация.

### 🧬 Pipeline

```plaintext
Вход (B, S) -> Embedding (B, S, emb_dim)
          -> CNN: Conv1d + MaxPool + Conv1d -> (B, S//2, emb_dim*4)
          -> AttentionPool -> (B, emb_dim*4)
          -> ReLU
          -> Transformer encoder + LearnedPositionalEncoding
          -> AttentionPool -> (B, hidden_size)
          -> MLP decoder -> [0,1]
````

---

## 🔒 encoder.py

Шифрует файлы с использованием **AES** и **ChaCha20**, ключ шифруется RSA.
Формат: `nonce + encoded_key + зашифрованные данные`

```bash
python encoder.py input_file output_AES_file;output_ChaCha20_file
```

---

## 🛠 prepare\_dataset.py

Подготавливает датасет: обрезает файлы, шифрует и раскладывает в папки:

- `prepared/normal/`
- `prepared/AES/`
- `prepared/ChaCha20/`

```bash
python prepare_dataset.py путь_до_папки
```

---

## ✨ Для чего

Нейросеть учится определять, зашифрован ли файл.
