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
import warnings

# Добавляем путь к models в sys.path для корректного импорта
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Импортируем НОВУЮ модель
from models.KAN.KANmodel import KANAutoEncoder  # Убедитесь, что путь правильный!
from autoencoder_dataset import AutoencoderDataset


def initialize_model():
    """
    Инициализирует НОВУЮ модель KANAutoEncoder с правильной конфигурацией
    """
    # НОВАЯ конфигурация слоев с точечным контролем KAN
    layer_configs = [
        {'out_channels': 32, 'kernel_size': 11, 'layer_type': 'conv'},
        {'out_channels': 128, 'kernel_size': 7, 'layer_type': 'conv'},
        {'out_channels': 256, 'kernel_size': 5, 'layer_type': 'kan', 
         'kan_params': {'grid_size': 5, 'spline_order': 3}},  # Только bottleneck - KAN
        {'out_channels': 128, 'kernel_size': 7, 'layer_type': 'conv'},
        {'out_channels': 32, 'kernel_size': 11, 'layer_type': 'conv'}
    ]

    # Инициализируем НОВУЮ модель
    model = KANAutoEncoder(
        vocab_size=256,           # Для байтовых значений (0-255)
        embed_dim=64,             # Размер векторов эмбеддинга
        layer_configs=layer_configs,
        use_batch_norm=True,      # Использовать нормализацию по батчам
        use_skip_connections=True, # Использовать skip соединения
        use_pool=False,           # КРИТИЧНО: отключаем пулинг для 1D данных!
        dropout_rate=0.1,
        base_activation=nn.GELU,
        kan_import_path=".torchKAN"  # Путь к вашей реализации KAN
    )
    
    # Выводим статистику параметров
    model.count_parameters()
    
    return model


def load_datasets(data_dir, validation_split=0.2, max_data_len=1024, corruption_ratio=0.1):
    """
    Загружает обучающий и валидационный датасеты
    """
    # Загружаем полный датасет (теперь он возвращает 3 значения!)
    full_dataset = AutoencoderDataset(
        data_dir=data_dir, 
        max_data_len=max_data_len,
        start_index=0,
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
    """
    # Создаем загрузчики данных (теперь обрабатывают 3 тензора)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True if torch.cuda.is_available() else False,
        # collate_fn не требуется - DataLoader автоматически обработает 3 тензора
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
    """
    # CrossEntropyLoss для многоклассовой классификации
    criterion = nn.CrossEntropyLoss()

    # Определяем оптимизатор Adam с заданными параметрами
    optimizer = optim.Adam(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay
    )

    # Настройка планировщика скорости обучения
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, 
        mode='min', 
        factor=0.5, 
        patience=3,
    )

    return criterion, optimizer, scheduler


def train_epoch(model, train_loader, criterion, optimizer, device):
    """
    Выполняет один эпоху обучения с МАСКИРОВАННЫМ LOSS
    """
    model.train()
    running_loss = 0.0
    total_masked_positions = 0  # Считаем количество поврежденных позиций для нормализации

    train_bar = tqdm(train_loader, desc="Training", leave=False)

    for corrupted_data, original_data, mask in train_bar:
        # Перемещаем данные на устройство
        corrupted_data = corrupted_data.to(device, non_blocking=True)
        original_data = original_data.to(device, non_blocking=True)
        mask = mask.to(device, non_blocking=True)

        # Обнуляем градиенты
        optimizer.zero_grad(set_to_none=True)  # Более эффективно для GPU

        # Прямой проход с передачей МАСКИ
        reconstructed = model(corrupted_data, mask)

        # === МАСКИРОВАННЫЙ LOSS только по поврежденным позициям ===
        batch_size, seq_len, vocab_size = reconstructed.shape
        
        # Разворачиваем тензоры для CrossEntropyLoss
        logits_flat = reconstructed.view(-1, vocab_size)  # (B*L, 256)
        targets_flat = original_data.view(-1)             # (B*L,)
        mask_flat = mask.view(-1)                          # (B*L,)
        
        # Выбираем только поврежденные позиции
        logits_masked = logits_flat[mask_flat]
        targets_masked = targets_flat[mask_flat]
        
        # Вычисляем loss только для поврежденных позиций
        if logits_masked.size(0) > 0:  # Защита от пустых батчей
            loss = criterion(logits_masked, targets_masked)
            total_masked_positions += mask_flat.sum().item()
        else:
            loss = torch.tensor(0.0, device=device, requires_grad=True)
            warnings.warn("Батч без поврежденных позиций!")

        # Обратный проход
        loss.backward()

        # Обновляем веса
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)  # Защита от exploding gradients
        optimizer.step()

        # Обновляем статистику
        running_loss += loss.item() * logits_masked.size(0)

        # Обновляем прогресс-бар
        train_bar.set_postfix({"Batch Loss": loss.item()})

    # Нормализуем loss по количеству поврежденных позиций
    if total_masked_positions > 0:
        epoch_loss = running_loss / total_masked_positions
    else:
        epoch_loss = float('inf')
        warnings.warn("Ни одной поврежденной позиции за эпоху!")
    
    return epoch_loss


def validate_epoch(model, val_loader, criterion, device):
    """
    Выполняет одну эпоху валидации с МАСКИРОВАННЫМ LOSS
    """
    model.eval()
    running_loss = 0.0
    total_masked_positions = 0

    with torch.no_grad():
        val_bar = tqdm(val_loader, desc="Validation", leave=False)

        for corrupted_data, original_data, mask in val_bar:
            corrupted_data = corrupted_data.to(device, non_blocking=True)
            original_data = original_data.to(device, non_blocking=True)
            mask = mask.to(device, non_blocking=True)

            # Прямой проход
            reconstructed = model(corrupted_data, mask)

            # Вычисляем МАСКИРОВАННЫЙ loss
            batch_size, seq_len, vocab_size = reconstructed.shape
            logits_flat = reconstructed.view(-1, vocab_size)
            targets_flat = original_data.view(-1)
            mask_flat = mask.view(-1)
            
            logits_masked = logits_flat[mask_flat]
            targets_masked = targets_flat[mask_flat]
            
            if logits_masked.size(0) > 0:
                loss = criterion(logits_masked, targets_masked)
                running_loss += loss.item() * logits_masked.size(0)
                total_masked_positions += mask_flat.sum().item()

            val_bar.set_postfix({"Batch Loss": loss.item() if logits_masked.size(0) > 0 else 0.0})

    # Нормализуем loss
    if total_masked_positions > 0:
        epoch_loss = running_loss / total_masked_positions
    else:
        epoch_loss = float('inf')
    
    return epoch_loss


def save_checkpoint(model, optimizer, epoch, loss, filepath):
    """
    Сохраняет контрольную точку модели
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
    Обучает модель с поддержкой маскирования
    """
    if save_checkpoints:
        os.makedirs(checkpoint_dir, exist_ok=True)

    # Инициализируем НОВУЮ модель
    model = initialize_model()

    # Определяем устройство
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Используемое устройство: {device}")
    print(f"Модель перемещена на {device}")

    # Перемещаем модель на устройство
    model = model.to(device)

    # Загружаем датасеты
    train_dataset, val_dataset = load_datasets(
        data_dir, 
        validation_split=validation_split, 
        max_data_len=max_data_len,
        corruption_ratio=corruption_ratio
    )

    print(f"Размер обучающего датасета: {len(train_dataset)}")
    print(f"Размер валидационного датасета: {len(val_dataset)}")

    # Настраиваем загрузчики данных
    train_loader, val_loader = setup_data_loaders(
        train_dataset, 
        val_dataset, 
        batch_size=batch_size,
        num_workers=4 if torch.cuda.is_available() else 0
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
        print(f"Обучающая потеря (только по поврежденным позициям): {train_loss:.4f}")

        # Валидация
        val_loss = validate_epoch(model, val_loader, criterion, device)
        print(f"Потеря на валидации (только по поврежденным позициям): {val_loss:.4f}")

        # Обновляем планировщик
        scheduler.step(val_loss)

        # Сохраняем контрольную точку, если потери улучшились
        if save_checkpoints and val_loss < best_val_loss:
            best_val_loss = val_loss
            checkpoint_path = os.path.join(checkpoint_dir, f"best_model_epoch_{epoch+1}.pth")
            save_checkpoint(model, optimizer, epoch, val_loss, checkpoint_path)
            print(f"💾 Сохранена ЛУЧШАЯ модель с потерей: {best_val_loss:.4f} в {checkpoint_path}")

        # Сохраняем контрольную точку каждые 5 эпох
        if save_checkpoints and (epoch + 1) % 5 == 0:
            checkpoint_path = os.path.join(checkpoint_dir, f"checkpoint_epoch_{epoch+1}.pth")
            save_checkpoint(model, optimizer, epoch, val_loss, checkpoint_path)
            print(f"💾 Сохранена контрольная точка эпохи {epoch+1} в {checkpoint_path}")

    # Сохраняем окончательную модель
    if save_checkpoints:
        final_path = os.path.join(checkpoint_dir, "final_model.pth")
        save_checkpoint(model, optimizer, num_epochs-1, val_loss, final_path)
        print(f"💾 Сохранена окончательная модель в {final_path}")

    print("\n🎉 Обучение успешно завершено!")


def main():
    """
    Основная функция для запуска обучения
    """
    parser = argparse.ArgumentParser(description="Обучение автоэнкодера с KAN свертками и маскированием")
    parser.add_argument("--data_dir", type=str, default="train/data/markup", 
                        help="Директория с данными")
    parser.add_argument("--num_epochs", type=int, default=50, 
                        help="Количество эпох обучения")
    parser.add_argument("--batch_size", type=int, default=32,  # Увеличено для стабильности
                        help="Размер батча")
    parser.add_argument("--learning_rate", type=float, default=0.001,  # Снижено для стабильности
                        help="Скорость обучения")
    parser.add_argument("--validation_split", type=float, default=0.2, 
                        help="Доля данных для валидации")
    parser.add_argument("--max_data_len", type=int, default=10240,  # Фиксированная длина для модели
                        help="Длина последовательности для обучения")
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
    # Устанавливаем точность для GPU
    torch.set_float32_matmul_precision('high')  # Для Ampere GPU и новее
    
    # Отключаем параллелизм OpenMP для DataLoader
    os.environ["OMP_NUM_THREADS"] = "1" 
    
    main()