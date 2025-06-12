import torch
import torch.nn as nn
import torch.optim as optim
import math
import utils

class BaseTransformer(nn.Module):
    def __init__(self, vocab_size, classes, d_model=512, nhead=8, num_layers=2, max_len=256):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.pos_encoder = utils.LearnedPositionalEncoding(max_len, d_model)

        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        self.attention = nn.Sequential(
            nn.Linear(d_model, d_model//2),
            nn.ReLU(),
            nn.Linear(d_model//2, 1)
        )
        
        self.decoder = nn.Linear(d_model, classes)
        
    def forward(self, x):
        x = self.embedding(x)
        x = self.pos_encoder(x)
        x = x.transpose(0, 1)
        x = self.transformer_encoder(x).transpose(0,1)
        w = self.attention(x)
        w = torch.softmax(w, dim=1)
        x = torch.sum(x*w, dim=1)
        x = self.decoder(x)
        return torch.sigmoid(x)
    
    
        
        
        