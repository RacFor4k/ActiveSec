import os
import math
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from collections import Counter
import tqdm
import random

class NNDataset(Dataset):

    def __init__(self, read_len = 256, offset = 0, randomise_offset = 0, classes = 2):
        super().__init__()
        self.read_len = read_len
        self.offset = offset
        self.randomise_offset = randomise_offset
        self.classes = classes
        if not os.path.exists('dataset\\'):
            raise "Dataset not found! run generateDataset.py"
        self.len = len(os.listdir('dataset\\'))
        self.len = 300 

    def __len__(self):
        return self.len
    
    def __getitem__(self, index):
        file = f'dataset\\{index*self.classes//self.len}_{index%(self.len//self.classes)}'
        with open(file, 'rb') as fs:
            offset = self.offset+random.randint(0,self.randomise_offset) 
            if offset+self.read_len > os.path.getsize(file):
                offset = 0
            fs.seek(offset)
            data = list(fs.read(self.read_len))
            out = index*self//self.len
            return torch.tensor([data], dtype=torch.float32), out
        
class ByteClassifier(nn.Module):
    def __init__(self, classes):
        super(ByteClassifier, self).__init__()
        self.classes = classes

        # Сверточные слои
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=16, kernel_size=3, stride=2, padding=1)
        self.conv2 = nn.Conv1d(in_channels=16, out_channels=32, kernel_size=3, stride=2, padding=1)
        self.conv3 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=3, stride=2, padding=1)
        
        # Полносвязные слои
        self.fc1 = nn.Linear(64 * 4, 128)  # Размерность будет вычислена после подсчета
        self.fc2 = nn.Linear(128, self.classes)  # 2 класса: является, не является
        
        # Функция активации
        self.relu = nn.ReLU()
        self.maxpool = nn.MaxPool1d(kernel_size=2, stride=2)
        self.softmax = nn.Softmax(dim=1)
        
    def forward(self, x):
        # Применяем свертки с активацией
        x = self.relu(self.conv1(x))
        x = self.maxpool(x)
        x = self.relu(self.conv2(x))
        x = self.maxpool(x)
        x = self.relu(self.conv3(x))
        x = self.maxpool(x)
        
        # Преобразуем в плоскую форму для входа в полносвязные слои
        x = x.view(x.size(0), -1)  # Выпрямляем
        
        # Пропускаем через полносвязные слои
        x = self.relu(self.fc1(x))
        x = self.fc2(x)
        
        return self.softmax(x)