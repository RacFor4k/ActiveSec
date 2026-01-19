import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
import argparse
import os
import logging
from pathlib import Path
from tqdm import tqdm
import sys
from pathlib import Path

# Добавляем путь к models в sys.path для корректного импорта
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from models.KAN.KANmodel import KANAutoEncoder
from autoencoder_dataset import AutoencoderDataset


def initialize_model():
    """
    Инициализирует модель KANAutoEncoder с подходящими параметрами
    """
    # Архитектура модели: [[каналы, использовать KAN (0/1), размер ядра], ...]
    architecture = [[32, 0, 3], [128, 1, 3], [258, 1, 3], [128, 1, 3], [32, 0, 3]]

    # Инициализируем основную модель
    model = KANAutoEncoder(
        architecture=architecture,
        vocab_size=256,           # Для байтовых значений (0-255)
        embedding_dim=64,         # Размер векторов эмбеддинга
        use_batch_norm=True,      # Использовать нормализацию по батчам
        use_skip_connections=True # Использовать skip соединения
    )

    return model


def load_datasets(data_dir, validation_split=0.2, max_data_len=1024, corruption_ratio=0.1):
    """
    Загружает обучающий и валидационный датасеты

    Args:
        data_dir: директория с данными
        validation_split: доля данных для валидации
        max_data_len: максимальная длина данных
        corruption_ratio: доля байтов, которые будут удалены (заменены на 0)
    """

    # Загружаем полный датасет
    full_dataset = AutoencoderDataset(
        data_dir=data_dir, 
        max_data_len=max_data_len,
        corruption_ratio=corruption_ratio
    )

    # Вычисляем размеры для разделения
    val_size = int(validation_split * len(full_dataset))
    train_size = len(full_dataset) - val_size

    # Разделяем датасет на обучающую и валидационную части
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])
    return train_dataset, val_dataset


def setup_data_loaders(train_dataset, val_dataset, batch_size=32, num_workers=4):
    """
    Настраивает загрузчики данных для обучения и валидации

    Args:
        train_dataset: обучающий датасет
        val_dataset: валидационный датасет
        batch_size: размер батча
        num_workers: количество процессов для загрузки данных
    """
    # Создаем загрузчики данных
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True if torch.cuda.is_available() else False
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True if torch.cuda.is_available() else False
    )
    return train_loader, val_loader


def setup_optimizer_and_criterion(model, learning_rate=0.001, weight_decay=1e-4):
    """
    Настраивает оптимизатор и функцию потерь

    Args:
        model: модель для обучения
        learning_rate: скорость обучения
        weight_decay: коэффициент регуляризации
    """
    # Определяем функцию потерь для задачи восстановления (MSE Loss)
    criterion = nn.CrossEntropyLoss()

    # Определяем оптимизатор Adam с заданными параметрами
    optimizer = optim.Adam(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay
    )

    # Настройка планировщика скорости обучения (опционально)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer,'max', patience=2)

    return criterion, optimizer, scheduler


def train_epoch(model, train_loader, criterion, optimizer, device):
    """
    Выполняет один эпоху обучения

    Args:
        model: модель для обучения
        train_loader: загрузчик обучающих данных
        criterion: функция потерь
        optimizer: оптимизатор
        device: устройство для вычислений (CPU или GPU)
    """
    model.train()  # Устанавливаем модель в режим обучения
    running_loss = 0.0

    # Используем tqdm для отображения прогресса
    train_bar = tqdm(train_loader, desc="Training", leave=False)

    for corrupted_data, original_data in train_bar:
        # Перемещаем данные на устройство
        corrupted_data, original_data = corrupted_data.to(device), original_data.to(device)

        # Обнуляем градиенты
        optimizer.zero_grad()

        # Прямой проход
        reconstructed = model(corrupted_data)

        # Вычисляем потери
        # Изменяем форму для CrossEntropyLoss: (N, C, ...) -> (N*C, ...)
        batch_size, seq_len, vocab_size = reconstructed.shape
        loss = criterion(
            reconstructed.view(-1, vocab_size),  # (batch*seq_len, vocab_size)
            original_data.view(-1)              # (batch*seq_len,)
        )

        # Обратный проход
        loss.backward()

        # Обновляем веса
        optimizer.step()

        # Обновляем статистику
        running_loss += loss.item()

        # Обновляем прогресс-бар
        train_bar.set_postfix({"Loss": loss.item()})

    epoch_loss = running_loss / len(train_loader)
    return epoch_loss


def validate_epoch(model, val_loader, criterion, device):
    """
    Выполняет одну эпоху валидации

    Args:
        model: модель для валидации
        val_loader: загрузчик валидационных данных
        criterion: функция потерь
        device: устройство для вычислений (CPU или GPU)
    """
    model.eval()  # Устанавливаем модель в режим оценки
    running_loss = 0.0

    # Отключаем вычисление градиентов
    with torch.no_grad():
        val_bar = tqdm(val_loader, desc="Validation", leave=False)

        for corrupted_data, original_data in val_bar:
            # Перемещаем данные на устройство
            corrupted_data, original_data = corrupted_data.to(device), original_data.to(device)

            # Прямой проход
            reconstructed = model(corrupted_data)

            # Вычисляем потери
            batch_size, seq_len, vocab_size = reconstructed.shape
            loss = criterion(
                reconstructed.view(-1, vocab_size),  # (batch*seq_len, vocab_size)
                original_data.view(-1)              # (batch*seq_len,)
            )

            # Обновляем статистику
            running_loss += loss.item()

            # Обновляем прогресс-бар
            val_bar.set_postfix({"Loss": loss.item()})

    epoch_loss = running_loss / len(val_loader)
    return epoch_loss


def save_checkpoint(model, optimizer, epoch, loss, filepath):
    """
    Сохраняет контрольную точку модели

    Args:
        model: модель для сохранения
        optimizer: оптимизатор
        epoch: текущая эпоха
        loss: текущее значение потерь
        filepath: путь для сохранения
    """
    checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': loss,
    }
    torch.save(checkpoint, filepath)


def train_model(data_dir, num_epochs=50, batch_size=32, learning_rate=0.001, 
                validation_split=0.2, max_data_len=1024, corruption_ratio=0.1,
                save_checkpoints=True, checkpoint_dir="./checkpoints"):
    """
    Обучает модель

    Args:
        data_dir: директория с данными
        num_epochs: количество эпох обучения
        batch_size: размер батча
        learning_rate: скорость обучения
        validation_split: доля данных для валидации
        max_data_len: максимальная длина данных
        corruption_ratio: доля байтов, которые будут удалены (заменены на 0)
        save_checkpoints: сохранять ли контрольные точки
        checkpoint_dir: директория для сохранения контрольных точек
    """
    # Создаем директорию для контрольных точек, если она не существует
    if save_checkpoints:
        os.makedirs(checkpoint_dir, exist_ok=True)

    # Инициализируем модель
    model = initialize_model()

    # Определяем устройство для вычислений
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Используемое устройство: {device}")

    # Перемещаем модель на устройство
    model.to(device)

    # Загружаем датасеты
    train_dataset, val_dataset = load_datasets(
        data_dir, 
        validation_split=validation_split, 
        max_data_len=max_data_len,
        corruption_ratio=corruption_ratio
    )

    # Настраиваем загрузчики данных
    train_loader, val_loader = setup_data_loaders(
        train_dataset, 
        val_dataset, 
        batch_size=batch_size
    )

    # Настраиваем оптимизатор и функцию потерь
    criterion, optimizer, scheduler = setup_optimizer_and_criterion(
        model, 
        learning_rate=learning_rate
    )

    # Лучшее значение потерь для сохранения лучшей модели
    best_val_loss = float('inf')

    # Обучаем модель
    for epoch in range(num_epochs):
        print(f"\nЭпоха {epoch+1}/{num_epochs}")
        print("-" * 30)

        # Обучение
        train_loss = train_epoch(model, train_loader, criterion, optimizer, device)
        print(f"Обучающая потеря: {train_loss:.4f}")

        # Валидация
        val_loss = validate_epoch(model, val_loader, criterion, device)
        print(f"Потеря на валидации: {val_loss:.4f}")

        # Обновляем планировщик
        scheduler.step()

        # Сохраняем контрольную точку, если потери улучшились
        if save_checkpoints and val_loss < best_val_loss:
            best_val_loss = val_loss
            checkpoint_path = os.path.join(checkpoint_dir, f"best_model.pth")
            save_checkpoint(model, optimizer, epoch, val_loss, checkpoint_path)
            print(f"Сохранена лучшая модель с потерей: {best_val_loss:.4f}")

        # Сохраняем контрольную точку каждые 10 эпох
        if save_checkpoints and (epoch + 1) % 10 == 0:
            checkpoint_path = os.path.join(checkpoint_dir, f"checkpoint_epoch_{epoch+1}.pth")
            save_checkpoint(model, optimizer, epoch, val_loss, checkpoint_path)
            print(f"Сохранена контрольная точка эпохи {epoch+1}")

    # Сохраняем окончательную модель
    if save_checkpoints:
        final_path = os.path.join(checkpoint_dir, "final_model.pth")
        save_checkpoint(model, optimizer, num_epochs-1, val_loss, final_path)
        print(f"Сохранена окончательная модель")

    print("\nОбучение завершено!")


def main():
    """
    Основная функция для запуска обучения
    """
    parser = argparse.ArgumentParser(description="Обучение автоэнкодера с KAN свертками")
    parser.add_argument("--data_dir", type=str, default="train/data/markup", 
                        help="Директория с данными")
    parser.add_argument("--num_epochs", type=int, default=50, 
                        help="Количество эпох обучения")
    parser.add_argument("--batch_size", type=int, default=32, 
                        help="Размер батча")
    parser.add_argument("--learning_rate", type=float, default=0.001, 
                        help="Скорость обучения")
    parser.add_argument("--validation_split", type=float, default=0.2, 
                        help="Доля данных для валидации")
    parser.add_argument("--max_data_len", type=int, default=10240, 
                        help="Максимальная длина данных")
    parser.add_argument("--corruption_ratio", type=float, default=0.1, 
                        help="Доля байтов, которые будут удалены (заменены на 0)")
    parser.add_argument("--no_save", action="store_true", 
                        help="Не сохранять контрольные точки")
    parser.add_argument("--checkpoint_dir", type=str, default="./autoencoder_checkpoints", 
                        help="Директория для сохранения контрольных точек")

    args = parser.parse_args()

    # Запускаем обучение
    train_model(
        data_dir=args.data_dir,
        num_epochs=args.num_epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        validation_split=args.validation_split,
        max_data_len=args.max_data_len,
        corruption_ratio=args.corruption_ratio,
        save_checkpoints=not args.no_save,
        checkpoint_dir=args.checkpoint_dir
    )


if __name__ == "__main__":
    main()