import torch
import torch.nn as nn
import math

class SinusoidalPositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        self.pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        self.pe[:, 0::2] = torch.sin(position * div_term)  # чётные
        self.pe[:, 1::2] = torch.cos(position * div_term)  # нечётные
        self.pe = self.pe.unsqueeze(0)  # (1, max_len, d_model)
        
    def forward(self, x):
        return x + self.pe[:, :x.size(1)]

class LearnedPositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=256):
        super().__init__()
        self.pos_embedding = nn.Embedding(max_len, d_model)

    def forward(self, x):
        positions = torch.arange(0, x.size(1), device=x.device).unsqueeze(0)
        return x + self.pos_embedding(positions)
