from CryptoNet.Models.CNN_SentinelNet_1 import SentinelNet
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

class JudjeNetTrain(nn.Module):
    def __init__(self, input_size, hidden_size) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.cell = nn.GRUCell(input_size, hidden_size)
        self.out = nn.Linear(hidden_size, 1)
        self.sigm = nn.Sigmoid()
        
    #train
    def forward(self, x):
        batch_size, seq_len, _ = x.shape
        h = x.new_zeros(batch_size, self.hidden_size)
        for t in range(seq_len):
            inp = x[:, t, :]
            h = self.cell(inp, h)
        out = self.sigm(self.out(h))
        return out

class JudjeNet(JudjeNetTrain):
    def __init__(self, input_size, hidden_size) -> None:
        super().__init__(input_size, hidden_size)
    
    #eval
    def forward(self, x, h):
        if h is None:
             h = x.new_zeros(self.hidden_size)
        h = self.cell(x,h)
        return self.sigm(self.out(h)), h