from CryptoAI.prototype.model import NN
from CryptoAI.prototype.dataset import CAIDataset
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import sys

"""
0 - train
1 - forward
"""
TYPE = 0 
BATCH_SIZE = 16
LEARNING_RATE = 0.001
NUM_EPOCH = 10
SAVE_RATE = 1 #каждую эпоху

def save(model, epoch = None):
    if not epoch:
        epoch = ''
    else:
        epoch = '_'+epoch
    torch.save(model.state_dict(), f'model{epoch}.pth')
    print('Модель сохранена в model.pth')

def train(model, loader):
    for epoch in range(NUM_EPOCH):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        for inputs, targets in loader:
            inputs, targets = inputs.to(device), targets.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * inputs.size(0)
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
        
        epoch_loss = running_loss / total
        epoch_acc = correct / total
        print(f'Epoch [{epoch+1}/{NUM_EPOCH}] Train loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}')

def forward(model, data):
    model.eval()
    with torch.no_grad():  
        data = torch.tensor(data)
        outputs = model(data)
        print(outputs)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = NN().to(device)
criterion = nn.BCEWithLogitsLoss()
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

if TYPE == 0:
    dataset = CAIDataset()
    loader = DataLoader(dataset,batch_size=16, shuffle=True)
    train(model, loader)
    