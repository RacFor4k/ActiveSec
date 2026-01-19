import torch
from torch.utils.data import Dataset
import os
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Optional, Callable, Tuple
import struct


class BinaryDataset(Dataset):
    """
    Класс Dataset для загрузки и обработки бинарных файлов для задач классификации
    """
    
    def __init__(self, 
                 data_dir: str, 
                 max_data_len: int = 9728,
                 start_index: int = 512,
                 transform: Optional[Callable] = None,
                 target_transform: Optional[Callable] = None):
        """
        Инициализация датасета
        
        Args:
            data_dir: путь к директории с данными
            transform: трансформации для данных
            target_transform: трансформации для меток
        """
        self.data_dir = Path(data_dir)
        self.max_data_len = min(max_data_len,10240-start_index)
        self.start_index = start_index
        self.transform = transform
        self.target_transform = target_transform

        with open(os.path.join(self.data_dir, 'label.txt'), 'r') as file:
            self.labels = file.readlines()
            self.labels = [label.split() for label in self.labels]

    
    def __len__(self) -> int:
        """
        Возвращает количество элементов в датасете
        """
        return len(self.labels)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Возвращает элемент датасета по индексу
        
        Args:
            idx: индекс элемента
            
        Returns:
            кортеж (данные, метка)
        """
        file_path = self.labels[idx][0]
        label = torch.tensor(int(self.labels[idx][1]))
        
        # Чтение бинарного файла
        with open(os.path.join(self.data_dir,file_path), 'rb') as f:
            chi2 = f.read(8)
            chi2 = torch.tensor(struct.unpack('d',chi2),dtype=torch.float32)
            file_content = f.read()
        
        # Преобразование в тензор PyTorch
        data_tensor = torch.tensor(np.frombuffer(file_content, dtype=np.uint8), dtype=torch.int)

        # Применение трансформаций, если они заданы
        if self.transform:
            data_tensor = self.transform(data_tensor)
        
        if self.target_transform:
            label = self.target_transform(label)    
        
        mask = (torch.rand(chi2.size(0)) > 0.5).float()
        chi2 = chi2 * mask 
        
        return data_tensor[self.start_index:self.start_index+self.max_data_len], label, chi2


# Пример использования
if __name__ == "__main__":
    # Пример создания датасета
    dataset = BinaryDataset(
        data_dir=r"train\data\markup",  # директория с данными
        # labels_file="path/to/labels.csv",  # файл с метками (опционально)
    )
    
    print(f"Размер датасета: {len(dataset)}")
    
    # Пример получения первого элемента
    if len(dataset) > 0:
        data, label, _ = dataset[8]
        print(f"Размер данных первого элемента: {data.shape}")
        print(f"Метка первого элемента: {label}   {_}")