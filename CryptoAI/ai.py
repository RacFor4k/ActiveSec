import os
import math
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from collections import Counter
import tqdm
from cryptoAI import NNDataset, ByteClassifier

CLASSES = 2

def train(model, optimizer, criterion, device, dataloader):
    for epoch in range(20):
        model.train()
        total_loss = []
        for x, y in tqdm.tqdm(dataloader, disable=True):
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            output = model(x)
            #print(output, y)
            loss = criterion(output, y)
            loss.backward()
            optimizer.step()
            total_loss += [loss.item()]
            #print(1+loss, '\t', output[-1], y[-1])
        print(f"Epoch {epoch+1}, Loss: {(sum(total_loss)/len(total_loss)):.4f}")
        #if abs(sum(total_loss)/len(total_loss)) > 0.6:
         #   break


        torch.save(model.state_dict(), f'weights\\model_{epoch}.pth')



def main():
    dataset = NNDataset(read_len= 256, offset= 512, randomise_offset=512, classes=CLASSES)
    dataloader = DataLoader(dataset, 1, True)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    # model = CryptoRecognice().to(device)
    model = ByteClassifier(classes=CLASSES).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.00005)
    criterion = nn.NLLLoss()

    if not os.path.exists('weights\\'):
        os.mkdir('weights\\')

    print(device)

    train(model, optimizer, criterion, device, dataloader)

if __name__ == '__main__':
    main()