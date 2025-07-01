from model import NN
from dataset import CAIDataset
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import sys
import tqdm

"""
0 - train
1 - forward
"""
TYPE = 0 
BATCH_SIZE = 16
LEARNING_RATE = 0.001
NUM_EPOCH = 20
SAVE_RATE = 1 #каждую эпоху

def save(model, epoch = None):
    if not epoch:
        epoch = ''
    else:
        epoch = '_'+str(epoch)
    torch.save(model.state_dict(), f'model{epoch}.pth')
    print('Модель сохранена в model.pth')

def train(model, loader, d):
    for epoch in range(NUM_EPOCH):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        for inputs, targets in tqdm.tqdm(loader):
            inputs, targets = inputs.to(device), targets.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * inputs.size(0)
            total += targets.size(0)
            correct += outputs.eq(targets).sum().item()
        
        epoch_loss = running_loss / total
        epoch_acc = correct / total
        print(f'Epoch [{epoch+1}/{NUM_EPOCH}] Train loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}', d.a)
        save(model, epoch+1)

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
    dataset = CAIDataset(offset=0)
    loader = DataLoader(dataset,batch_size=256, shuffle=True)
    train(model, loader, dataset)
    