import torch
import torch.nn as nn
import torch.optim as optim
import math
import utils as u

class CNN_1D(nn.Module):
    def __init__(self, in_chanels, hidden_chanels):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels=in_chanels, out_channels=hidden_chanels, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(in_channels=hidden_chanels, out_channels=hidden_chanels*2, kernel_size=3, padding=1)
        self.conv3 = nn.Conv1d(in_channels=hidden_chanels*2, out_channels=hidden_chanels*4, kernel_size=3, padding=1)
        self.max_pool = nn.MaxPool1d(kernel_size=3,stride=1)
        self.relu = nn.ReLU()
        self.g_pool = u.GlobalAvgPool1D()
         