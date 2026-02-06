import models.KAN.torchKAN as KAN
from tqdm import tqdm 
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

# 1. Настройки и устройство (GPU или CPU)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Используем устройство: {device}")

# Гиперпараметры
BATCH_SIZE = 256
LEARNING_RATE = 0.001
EPOCHS = 5

# 2. Подготовка данных (используем MNIST, который популярен на Kaggle)
# Преобразуем картинки в тензоры и нормализуем их (среднее 0.5, стд 0.5)
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,))
])

# Скачиваем обучающую и тестовую выборки
train_dataset = datasets.MNIST(root='./data', train=True, transform=transform, download=True)
test_dataset = datasets.MNIST(root='./data', train=False, transform=transform, download=True)

train_loader = DataLoader(dataset=train_dataset, batch_size=BATCH_SIZE, shuffle=True)
test_loader = DataLoader(dataset=test_dataset, batch_size=BATCH_SIZE, shuffle=False)

# 3. Создание примитивной MLP сети
class SimpleMLP(nn.Module):
    def __init__(self):
        super(SimpleMLP, self).__init__()
        # Вход: картинка 28x28 = 784 пикселя
        # Скрытый слой: 128 нейронов
        # Выход: 10 классов (цифры от 0 до 9)
        self.flatten = nn.Flatten()
        self.layers = nn.Sequential(
            KAN.KANLinear(28 * 28, 10,grid_size=3,spline_order=1),  # Входной слой -> Скрытый
            )

    def forward(self, x):
        x = self.flatten(x) # Разворачиваем картинку [Batch, 1, 28, 28] -> [Batch, 784]
        logits = self.layers(x)
        return logits

model = SimpleMLP().to(device)

# 4. Функция потерь и оптимизатор
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

# 5. Цикл обучения
for epoch in range(EPOCHS):
    model.train() # Режим обучения
    running_loss = 0.0
    
    for images, labels in tqdm(train_loader):
        images, labels = images.to(device), labels.to(device)
        
        # Прямой проход (Forward pass)
        outputs = model(images)
        loss = criterion(outputs, labels)
        
        # Обратный проход (Backward pass) и оптимизация
        optimizer.zero_grad() # Обнуляем градиенты
        loss.backward()       # Считаем градиенты
        optimizer.step()      # Обновляем веса
        
        running_loss += loss.item()
    
    print(f"Эпоха [{epoch+1}/{EPOCHS}], Потери: {running_loss/len(train_loader):.4f}")

# 6. Проверка точности (Evaluation)
model.eval() # Режим оценки (выключает dropout и т.д.)
correct = 0
total = 0

with torch.no_grad(): # Отключаем расчет градиентов для ускорения
    for images, labels in test_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        _, predicted = torch.max(outputs.data, 1) # Выбираем класс с макс. вероятностью
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

print(f"Точность на тестовых данных: {100 * correct / total:.2f}%")

KAN.count_prunable_kan_connections(model, 0.1)