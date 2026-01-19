import torch
from torch.utils.data import Dataset
import os
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Optional, Callable, Tuple


class AutoencoderDataset(Dataset):
    """
    Класс Dataset для загрузки и обработки бинарных файлов для задачи автоэнкодера
    Модели необходимо из входного буфера в котором удалено (=0) 10% байт восстановить исходный буффер
    """

    def __init__(self,
                 data_dir: str,
                 max_data_len: int = 9728,
                 start_index: int = 512,
                 transform: Optional[Callable] = None,
                 corruption_ratio: float = 0.1):  # 10% байтов будут удалены
        """
        Инициализация датасета

        Args:
            data_dir: путь к директории с данными
            max_data_len: максимальная длина данных
            start_index: начальный индекс для среза данных
            transform: трансформации для данных
            corruption_ratio: доля байтов, которые будут удалены (заменены на 0)
        """
        self.data_dir = Path(data_dir)
        self.max_data_len = min(max_data_len, 10240 - start_index)
        self.start_index = start_index
        self.transform = transform
        self.corruption_ratio = corruption_ratio

        # Читаем список файлов из label.txt
        with open(os.path.join(self.data_dir, 'label.txt'), 'r') as file:
            self.labels = file.readlines()
            self.labels = [label.split()[0] for label in self.labels]  # Берем только пути к файлам


    def __len__(self) -> int:
        """
        Возвращает количество элементов в датасете
        """
        return len(self.labels)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Возвращает элемент датасета по индексу

        Args:
            idx: индекс элемента

        Returns:
            кортеж (поврежденные_данные, оригинальные_данные)
        """
        file_path = self.labels[idx]

        # Чтение бинарного файла
        with open(os.path.join(self.data_dir, file_path), 'rb') as f:
            f.seek(8)
            file_content = f.read()

        # Преобразование в тензор PyTorch
        original_data = torch.tensor(np.frombuffer(file_content, dtype=np.uint8), dtype=torch.long)

        # Применяем срез данных
        original_data = original_data[self.start_index:self.start_index + self.max_data_len]

        # Создаем поврежденную версию данных (удаляем 10% байтов, заменяя их на 0)
        corrupted_data = original_data.clone()
        
        # Определяем индексы, которые будем "удалять"
        mask = (torch.rand(corrupted_data.size(0)) > self.corruption_ratio)
        # Заменяем выбранные байты на 0
        corrupted_data *= mask

        # Применение трансформаций, если они заданы
        if self.transform:
            corrupted_data = self.transform(corrupted_data)

        return corrupted_data, original_data


# Пример использования
if __name__ == "__main__":
    # Пример создания датасета
    dataset = AutoencoderDataset(
        data_dir=r"train\data\markup",  # директория с данными
        corruption_ratio=0.1  # 10% байтов будут удалены
    )

    print(f"Размер датасета: {len(dataset)}")

    # Пример получения первого элемента
    if len(dataset) > 0:
        corrupted, original = dataset[0]
        print(f"Размер поврежденных данных: {corrupted.shape}")
        print(f"Размер оригинальных данных: {original.shape}")
        
        # Подсчитываем количество измененных байтов
        diff_count = torch.sum(corrupted != original).item()
        print(f"Количество измененных байтов: {diff_count}")