import torch
import torch.nn as nn

class LearnedPositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=256):
        super().__init__()
        self.pos_embedding = nn.Embedding(max_len, d_model)

    def forward(self, x):
        positions = torch.arange(0, x.size(1), device=x.device).unsqueeze(0)
        return x + self.pos_embedding(positions)

class NN(nn.Module):
    class CNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1 = nn.Conv1d(
                in_channels=1,
                out_channels=16,
                kernel_size=3,
                padding=1
            )
            self.maxpool = nn.MaxPool1d(
                kernel_size=2,
                stride=2,
            ) 
            self.conv2 = nn.Conv1d(
                in_channels=16,
                out_channels=64,
                kernel_size=3,
                padding=1
            )
            self.relu = nn.ReLU()
            
        def forward(self, x):
            x = self.conv1(x)
            x = self.relu(x)
            x = self.maxpool(x)
            x = self.conv2(x)
            x = self.relu(x)
            return x
    
    class Transforemer(nn.Module):
        def __init__(self):
            
    
    def __init__(self, embedding_dim = 8, d_model):
        super().__init__()
        
        self.emb = nn.Embedding(256, embedding_dim=embedding_dim)
        self.conv = NN.CNN()
        self.relu = nn.ReLU()
        self.time_emb = LearnedPositionalEncoding(self)
        
        