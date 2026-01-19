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

from models.main_model import SequentialBinaryCNN as AS_NET, ExtrasToFeaturesFC
from dataset import BinaryDataset


def initialize_model():
    """
    Инициализирует модель SequentialBinaryCNN с подходящими параметрами
    """
    # Создаем модуль для обработки дополнительных признаков (chi2)
    extras_module = ExtrasToFeaturesFC(in_features=1, hidden=[16, 32])

    # Инициализируем основную модель
    model = AS_NET(
        extras_module=extras_module,
        vocab_size=256,           # Для байтовых значений (0-255)
        embedding_dim=64,         # Размер векторов эмбеддинга
        num_classes=2,            # Бинарная классификация (зашифрованные vs незашифрованные)
        conv_channels=[64, 128, 256, 512],  # Каналы для сверточных слоев
        kernel_sizes=[7, 5, 3, 3],        # Размеры ядра для сверточных слоев
        use_batch_norm=True      # Использовать нормализацию по батчам
    )

    return model


def load_datasets(data_dir, validation_split=0.2, max_data_len=1024):
    """
    Загружает обучающий и валидационный датасеты

    Args:
        data_dir: директория с данными
        validation_split: доля данных для валидации
    """

    # Загружаем полный датасет
    full_dataset = BinaryDataset(data_dir=data_dir, max_data_len=max_data_len)

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
    # Определяем функцию потерь для бинарной классификации
    criterion = nn.CrossEntropyLoss()

    # Определяем оптимизатор Adam с заданными параметрами
    optimizer = optim.Adam(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay
    )

    # Настройка планировщика скорости обучения (опционально)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.1)

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
    correct_predictions = 0
    total_samples = 0

    # Используем tqdm для отображения прогресса
    train_bar = tqdm(train_loader, desc="Training", leave=False)

    for data, targets, extras in train_bar:
        # Перемещаем данные на устройство
        data, targets = data.to(device), targets.to(device)
        
        extras = extras.to(device)
        torch.log(extras)

        # Обнуляем градиенты
        optimizer.zero_grad()

        # Прямой проход
        outputs = model(data, extras)
        loss = criterion(outputs, targets)

        # Обратный проход
        loss.backward()
        optimizer.step()

        # Статистика
        running_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        total_samples += targets.size(0)
        correct_predictions += (predicted == targets).sum().item()

        # Обновляем tqdm с текущими значениями потерь и точности
        train_bar.set_postfix({
            'Loss': f'{loss.item():.4f}',
            'Acc': f'{100. * correct_predictions / total_samples:.2f}%'
        })

    epoch_loss = running_loss / len(train_loader)
    epoch_acc = 100. * correct_predictions / total_samples

    return epoch_loss, epoch_acc


def validate_epoch(model, val_loader, criterion, device):
    """
    Выполняет один эпох валидации

    Args:
        model: модель для валидации
        val_loader: загрузчик валидационных данных
        criterion: функция потерь
        device: устройство для вычислений (CPU или GPU)
    """
    import time
    import psutil
    import GPUtil

    model.eval()  # Устанавливаем модель в режим оценки
    running_loss = 0.0
    correct_predictions = 0
    total_samples = 0

    # Дополнительные метрики
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    true_negatives = 0

    # Статистика использования ресурсов
    start_time = time.time()
    memory_percent = psutil.virtual_memory().percent

    # Отключаем вычисление градиентов
    with torch.no_grad():
        # Используем tqdm для отображения прогресса
        val_bar = tqdm(val_loader, desc="Validation", leave=False)

        for data, targets, extras in val_bar:
            # Перемещаем данные на устройство
            data, targets = data.to(device), targets.to(device)
            
            batch_size = data.size(0)

            # 2. Создаем тензор нулей формы (Batch_Size, 1)
            # 1 - это количество дополнительных признаков (у вас это chi2, значит 1)
            extras = torch.zeros((batch_size, 1), dtype=torch.float32).to(device)
            torch.log(extras)

            # Прямой проход
            outputs = model(data, extras)
            loss = criterion(outputs, targets)

            # Статистика
            running_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total_samples += targets.size(0)
            correct_predictions += (predicted == targets).sum().item()

            # Подсчет TP, FP, FN, TN для бинарной классификации
            for i in range(len(targets)):
                if targets[i] == 1 and predicted[i] == 1:
                    true_positives += 1
                elif targets[i] == 0 and predicted[i] == 1:
                    false_positives += 1
                elif targets[i] == 1 and predicted[i] == 0:
                    false_negatives += 1
                else:
                    true_negatives += 1

            # Обновляем tqdm с текущими значениями потерь и точности
            val_bar.set_postfix({
                'Loss': f'{loss.item():.4f}',
                'Acc': f'{100. * correct_predictions / total_samples:.2f}%'
            })

    epoch_loss = running_loss / len(val_loader)
    epoch_acc = 100. * correct_predictions / total_samples

    # Вычисляем дополнительные метрики
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    specificity = true_negatives / (true_negatives + false_positives) if (true_negatives + false_positives) > 0 else 0

    # Время выполнения
    execution_time = time.time() - start_time

    # Статистика использования ресурсов
    final_memory_percent = psutil.virtual_memory().percent

    # Формируем словарь с дополнительной статистикой
    validation_stats = {
        'loss': epoch_loss,
        'accuracy': epoch_acc,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'specificity': specificity,
        'execution_time': execution_time,
        'memory_usage': (memory_percent + final_memory_percent) / 2,
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'true_negatives': true_negatives
    }

    return epoch_loss, epoch_acc, validation_stats


def save_model(model, optimizer, epoch, train_loss, val_loss, val_acc, filepath):
    """
    Сохраняет модель и информацию о тренировке

    Args:
        model: модель для сохранения
        optimizer: оптимизатор
        epoch: текущая эпоха
        train_loss: потери на обучающей выборке
        val_loss: потери на валидационной выборке
        val_acc: точность на валидационной выборке
        filepath: путь для сохранения модели
    """
    # Создаем словарь с информацией о модели
    model_checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'train_loss': train_loss,
        'val_loss': val_loss,
        'val_acc': val_acc
    }

    # Сохраняем модель
    torch.save(model_checkpoint, filepath)
    print(f"Модель сохранена в {filepath}")


def load_model(model, optimizer, filepath, device):
    """
    Загружает сохраненную модель

    Args:
        model: модель для загрузки
        optimizer: оптимизатор
        filepath: путь к сохраненной модели
        device: устройство для вычислений
    """
    try:
        # Загружаем сохраненную модель
        checkpoint = torch.load(filepath, map_location=device)

        # Восстанавливаем состояние модели и оптимизатора
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        # Возвращаем информацию о последней эпохе и метриках
        epoch = checkpoint['epoch']
        train_loss = checkpoint['train_loss']
        val_loss = checkpoint['val_loss']
        val_acc = checkpoint['val_acc']

        print(f"Модель успешно загружена из {filepath}")
        return epoch, train_loss, val_loss, val_acc
    except FileNotFoundError:
        print(f"Файл {filepath} не найден. Обучение начнется с нуля.")
        return 0, float('inf'), float('inf'), 0.0
    except KeyError as e:
        print(f"Ошибка при загрузке модели: отсутствует ключ {e} в файле {filepath}")
        return 0, float('inf'), float('inf'), 0.0
    except Exception as e:
        print(f"Неизвестная ошибка при загрузке модели: {e}")
        return 0, float('inf'), float('inf'), 0.0


def setup_logging(log_file='training.log'):
    """
    Настраивает логирование для тренировки модели

    Args:
        log_file: путь к файлу логов
    """
    # Создаем форматер для логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Создаем обработчик для записи в файл
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Настраиваем логгер
    logger = logging.getLogger('AS-NET-Training')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def parse_arguments():
    """
    Разбирает аргументы командной строки
    """
    parser = argparse.ArgumentParser(description='Обучение модели AS-NET для классификации шифрования')

    parser.add_argument('--data_dir', type=str, default='train/data/markup',
                        help='Директория с обучающими данными')
    parser.add_argument('--validation_split', type=float, default=0.2,
                        help='Доля данных для валидации')
    parser.add_argument('--batch_size', type=int, default=32,
                        help='Размер батча')
    parser.add_argument('--num_workers', type=int, default=4,
                        help='Количество процессов для загрузки данных')
    parser.add_argument('--learning_rate', type=float, default=0.001,
                        help='Скорость обучения')
    parser.add_argument('--weight_decay', type=float, default=1e-4,
                        help='Коэффициент регуляризации')
    parser.add_argument('--num_epochs', type=int, default=50,
                        help='Количество эпох обучения')
    parser.add_argument('--checkpoint_dir', type=str, default='checkpoints',
                        help='Директория для сохранения чекпоинтов')
    parser.add_argument('--checkpoint_interval', type=int, default=5,
                        help='Интервал сохранения чекпоинтов (в эпохах)')
    parser.add_argument('--load_checkpoint', type=str, default=None,
                        help='Путь к чекпоинту для загрузки')
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu',
                        help='Устройство для обучения (cuda/cpu)')
    parser.add_argument('--log_file', type=str, default='training.log',
                        help='Файл для логирования')

    return parser.parse_args()


def main():
    """
    Основная функция для обучения модели AS-NET
    """
    # Разбираем аргументы командной строки
    args = parse_arguments()

    # Настраиваем логирование
    logger = setup_logging(args.log_file)

    # Создаем директорию для чекпоинтов, если она не существует
    os.makedirs(args.checkpoint_dir, exist_ok=True)

    # Инициализируем модель
    model = initialize_model()
    model.to(args.device)

    # Загружаем датасеты
    train_dataset, val_dataset = load_datasets(args.data_dir, args.validation_split, 10240)
    train_loader, val_loader = setup_data_loaders(
        train_dataset, val_dataset, args.batch_size, args.num_workers
    )

    # Настраиваем оптимизатор и функцию потерь
    criterion, optimizer, scheduler = setup_optimizer_and_criterion(
        model, args.learning_rate, args.weight_decay
    )

    # Загружаем чекпоинт, если указан
    start_epoch = 0
    if args.load_checkpoint:
        start_epoch, _, _, _ = load_model(model, optimizer, args.load_checkpoint, args.device)

    # Логируем начало обучения
    logger.info(f"Начинаем обучение с эпохи {start_epoch + 1}")
    print(f"Обучение на устройстве: {args.device}")

    # Переменные для отслеживания лучшей модели
    best_val_acc = 0.0
    best_val_loss = float('inf')

    # Цикл обучения
    for epoch in range(start_epoch, args.num_epochs):
        print(f"\nЭпоха {epoch + 1}/{args.num_epochs}")

        # Обучение
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, args.device)
        print(f"Обучающая потеря: {train_loss:.4f}, Обучающая точность: {train_acc:.2f}%")

        # Валидация
        val_loss, val_acc, val_stats = validate_epoch(model, val_loader, criterion, args.device)
        print(f"Валидационная потеря: {val_loss:.4f}, Валидационная точность: {val_acc:.2f}%")

        # Обновляем планировщик скорости обучения
        scheduler.step()

        # Логируем метрики
        logger.info(f"Эпоха {epoch + 1}: "
                    f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%, "
                    f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%")

        # Сохраняем лучшую модель
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_val_loss = val_loss
            checkpoint_path = os.path.join(args.checkpoint_dir, 'best_model.pth')
            save_model(model, optimizer, epoch + 1, train_loss, val_loss, val_acc, checkpoint_path)
            print(f"Лучшая модель сохранена с точностью {val_acc:.2f}%")

        # Сохраняем чекпоинт с заданным интервалом
        if (epoch + 1) % args.checkpoint_interval == 0:
            checkpoint_path = os.path.join(args.checkpoint_dir, f'checkpoint_epoch_{epoch + 1}.pth')
            save_model(model, optimizer, epoch + 1, train_loss, val_loss, val_acc, checkpoint_path)
            print(f"Чекпоинт сохранен: {checkpoint_path}")

    # Сохраняем финальную модель
    final_checkpoint_path = os.path.join(args.checkpoint_dir, 'final_model.pth')
    save_model(model, optimizer, args.num_epochs, train_loss, val_loss, val_acc, final_checkpoint_path)
    print(f"Финальная модель сохранена: {final_checkpoint_path}")

    # Выводим итоговую статистику
    print(f"\nОбучение завершено!")
    print(f"Лучшая валидационная точность: {best_val_acc:.2f}%")
    print(f"Лучшая валидационная потеря: {best_val_loss:.4f}")


if __name__ == "__main__":
    main()


