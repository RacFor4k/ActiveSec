import torch
import torch.nn as nn
import torch.optim as optim
import math

class GlobalAvgPool1D(nn.Module):
    def forward(self, x):
        # x: (batch, channels, length)
        return x.mean(dim=2)

class GlobalMaxPool1D(nn.Module):
    def forward(self, x):
        return x.max(dim=2)[0]

class GlobalAvgPool2D(nn.Module):
    def forward(self, x):
        # x: (batch, channels, height, width)
        return x.mean(dim=(2, 3))

class GlobalMaxPool2D(nn.Module):
    def forward(self, x):
        return x.max(dim=2)[0].max(dim=2)[0]
