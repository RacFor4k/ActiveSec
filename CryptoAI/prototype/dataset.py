import torch
from torch.utils.data import Dataset
import os
import random

class CustomDataset(Dataset):
    
    BASE_PATH = 'prepared'
    TYPES = ('normal, ChaCha20, AES')
    RAND = random.Random()
    
    def __init__(self, max_len = 512, rand_offset = False, offset = 0, dtype = torch.float32):
        self.max_len = max_len
        self.rand_offset = rand_offset
        self.offset = offset
        self.dtype = dtype
        self.info = self.get_info()
        self.len = len(self.info[0])
        self.full_len = self.len*3
    
    def get_info(self):
        normal = os.listdir(os.path.join(self.BASE_PATH, self.TYPES[0]))
        ChaCha20 = os.listdir(os.path.join(self.BASE_PATH, self.TYPES[1]))
        Aes = os.listdir(os.path.join(self.BASE_PATH, self.TYPES[2]))
        return normal, ChaCha20, Aes
    
    def __len__(self):
        return self.full_len

    def __getitem__(self, idx):
        idx, type = self.__parse__(idx)
        sample = self.__read_data__(idx, type)
        label = not(type == 0)
        return self.__tensor__(sample), self.__tensor__(label)
    
    def __parse__(self, idx):
        """
        0 - normal
        1 - ChaCha20
        2 - AES
        """
        type = idx % 3
        idx = idx % self.len
        return idx, type

    def __read_data__(self, idx, type):
        with open(os.path.join(self.BASE_PATH, self.TYPES[type], idx), 'rb') as file:
            offset = self.offset
            offset += self.RAND.randint(0,self.rand_offset)
            file.seek(offset)
            return file.read(self.max_len)
        
    def __tensor__(self, data):
        return torch.tensor(data=data, dtype=self.dtype)