import torch
from torch.utils.data import Dataset
import os
import random

#CAI - CryptoAI
class CAIDataset(Dataset):
    
    BASE_PATH = 'prepared'
    TYPES = ('normal', 'ChaCha20', 'AES')
    RAND = random.Random()
    PASS_SAPMLES = 1 #количество пропущенных файл к 1 прочитаному   (5000%PASS_SAMPLE == 0)
    a = 0
    def __init__(self, max_len = 512, rand_offset = False, offset = 0, dtype_in = torch.int32, dtype_out = torch.float32):
        self.max_len = max_len
        self.rand_offset = rand_offset
        self.offset = offset
        self.dtype_in = dtype_in
        self.dtype_out = dtype_out
        self.info = self.get_info()
        self.len = len(self.info[0])//self.PASS_SAPMLES
        self.full_len = self.len*2
    
    def get_info(self):
        normal = os.listdir(os.path.join(self.BASE_PATH, self.TYPES[0]))
        ChaCha20 = os.listdir(os.path.join(self.BASE_PATH, self.TYPES[1]))
        Aes = os.listdir(os.path.join(self.BASE_PATH, self.TYPES[2]))
        return normal, ChaCha20, Aes
    
    def __len__(self):
        return self.full_len

    def __getitem__(self, idx):
        idx, type = self.__parse__(idx)
        sample = [int(i) for i in self.__read_data__(idx, type)]
        label = not(type == 0)
        if label:
            self.a+=1
        else: 
            self.a-=1
        #print(self.TYPES[type], self.info[type][idx], '\t', label)
        return self.__tensor__(sample, self.dtype_in), self.__tensor__(label, self.dtype_out)
    
    def __parse__(self, idx):
        """
        0 - normal
        1 - ChaCha20
        2 - AES
        """
        type = idx % 2
        if type == 1:
            type += self.RAND.randint(0,1)
        idx = idx % self.len
        return idx, type

    def __read_data__(self, idx, type):
        with open(os.path.join(self.BASE_PATH, self.TYPES[type], self.info[type][idx*self.PASS_SAPMLES]), 'rb') as file:
            offset = self.offset
            offset += self.RAND.randint(0,self.rand_offset)
            file.seek(offset)
            return file.read(self.max_len)
        
    def __tensor__(self, data, dtype):
        return torch.tensor(data=data, dtype=dtype)