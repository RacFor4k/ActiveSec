import torch
import torch.nn as nn
import torch.nn.functional as F
import models.KAN.test.torchKAN as KAN

class ExtrasToFeaturesFC(nn.Module):
    """
    Модуль для преобразования дополнительных признаков (например, chi2) в вектор признаков

    :param in_features: int - количество входных признаков (по умолчанию 1)
    :param hidden: list - список размеров скрытых слоев (по умолчанию [16])
    """
    def __init__(self, in_features=1, hidden=[16]):
        super(ExtrasToFeaturesFC, self).__init__()

        # Сохраняем конфигурацию
        self.in_features = in_features
        self.hidden = hidden

        # Создаем полносвязные слои
        self.net = nn.ModuleList()
        if len(hidden) > 0:
            self.net.append(nn.Linear(in_features, hidden[0]))
            for i in range(1, len(hidden)):
                self.net.append(nn.Linear(hidden[i-1], hidden[i]))

    def forward(self, x):
        # Проход через полносвязные слои с активацией GELU
        for layer in self.net:
            x = layer(x)
            x = F.gelu(x)
        return x
    
    def features(self):
        return self.hidden[-1] if self.hidden else self.in_features






class SequentialBinaryCNN(nn.Module):
    """
    Основная модель для классификации последовательностей бинарных данных (байтов)

    :param extras_module: nn.Module - модуль получения фич из доп данных (chi2)
    :param vocab_size: int - размер словаря (по умолчанию 256 для байтовых значений 0-255)
    :param embedding_dim: int - размерность эмбеддинга (по умолчанию 64)
    :param num_classes: int - количество классов для классификации (по умолчанию 2)
    :param conv_channels: list - список количества каналов для сверточных слоев (по умолчанию [64, 128, 256])
    :param kernel_sizes: list - список размеров ядра для сверточных слоев (по умолчанию [3, 3, 3])
    :param use_batch_norm: bool - использовать ли batch нормализацию (по умолчанию True)
    """
    def __init__(self, extras_module: ExtrasToFeaturesFC, vocab_size=256, embedding_dim=64, num_classes=2, 
                 conv_channels=[64, 128, 256], kernel_sizes=[3, 3, 3], use_batch_norm=True):
        super(SequentialBinaryCNN, self).__init__()
        
        # Сохраняем конфигурацию
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.num_classes = num_classes
        self.conv_channels = conv_channels
        self.kernel_sizes = kernel_sizes
        self.use_batch_norm = use_batch_norm

        # Слой эмбеддинга для преобразования бинарного ввода в плотные векторы
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # Инициализируем сверточные слои в цикле
        self.conv_layers = nn.ModuleList()
        self.bn_layers = nn.ModuleList() if use_batch_norm else None

        # Создаем сверточные слои на основе предоставленной конфигурации
        in_channels = embedding_dim  # Входные каналы - это размерность эмбеддинга
        for i, out_channels in enumerate(conv_channels):
            kernel_size = kernel_sizes[i] if i < len(kernel_sizes) else kernel_sizes[-1]

            # Добавляем сверточный слой (используем 1D свертки для последовательных данных)
            conv_layer = nn.Conv1d(
                in_channels=in_channels,
                out_channels=out_channels,
                kernel_size=kernel_size,
                padding=kernel_size // 2,
                stride=1
            )
            self.conv_layers.append(conv_layer)

            # Добавляем слой нормализации по батчам, если указано
            if use_batch_norm and self.bn_layers is not None:
                bn_layer = nn.BatchNorm1d(out_channels)
                self.bn_layers.append(bn_layer)

            # Обновляем in_channels для следующего слоя
            in_channels = out_channels

        # Вычисляем размер для полносвязного слоя
        # Количество каналов - это последнее значение в conv_channels
        # После adaptive pooling размер будет (batch_size, channels, 1),
        # так что fc_input_size - это просто количество каналов
        fc_input_size = conv_channels[-1]  # Размер последнего канала

        self.extras_module = extras_module

        # Полносвязные слои
        # self.fc_layers = nn.ModuleList([
        #     nn.Linear(fc_input_size+self.extras_module.features(), 128),
        #     nn.Linear(128, num_classes)
        # ])
        self.fc_layers = nn.ModuleList([
            KAN.KANLinear(fc_input_size+self.extras_module.features(), 128, spline_order=1),
            KAN.KANLinear(128, num_classes, spline_order=1)
        ])

        # Слой дропаута
        self.dropout = nn.Dropout(0.5)

        # Инициализируем веса в цикле
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Инициализация весов с использованием различных методов инициализации в цикле"""
        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                # Инициализация сверточных слоев
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                # Инициализация полносвязных слоев
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Embedding):
                # Инициализация слоя эмбеддинга
                nn.init.normal_(m.weight, mean=0, std=0.1)
            elif isinstance(m, nn.BatchNorm1d):
                # Инициализация слоев батч-нормализации
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
    
    def forward(self, x, extras):
        # x shape: (batch_size, sequence_length) - содержит бинарные значения (0-255 для байтовых данных)

        # Применяем эмбеддинг: (batch_size, sequence_length) -> (batch_size, sequence_length, embedding_dim)
        x = self.embedding(x)

        # Транспонируем в (batch_size, embedding_dim, sequence_length) для Conv1d
        x = x.transpose(1, 2)

        # Проход по сверточным слоям
        for i, conv_layer in enumerate(self.conv_layers):
            x = conv_layer(x)

            # Применяем нормализацию по батчам, если доступна
            if self.use_batch_norm and i < len(self.bn_layers): # type: ignore
                x = self.bn_layers[i](x)  # type: ignore

            # Применяем функцию активации
            x = F.gelu(x)  # Используем GeLU - часто работает лучше, чем ReLU

            # Применяем max pooling после каждого сверточного блока
            x = F.max_pool1d(x, kernel_size=2, stride=2)

        # Применяем глобальный max pooling для получения фиксированного представления
        x = F.adaptive_max_pool1d(x, output_size=1)  # (batch_size, channels, 1)
        x = x.squeeze(2)  # (batch_size, channels)

        # Обрабатываем дополнительные признаки
        extras = self.extras_module(extras)  # (batch_size, features)

        # Конкатенируем признаки
        x = torch.cat((x, extras), dim=1)  # (batch_size, channels + features)

        # Проход по полносвязным слоям
        for i, fc_layer in enumerate(self.fc_layers):
            x = fc_layer(x)

            # Применяем функцию активации и dropout для всех слоев, кроме последнего
            if i < len(self.fc_layers) - 1:  # Не применяем активацию после последнего слоя
                x = F.gelu(x)  # Используем GeLU активацию между полносвязными слоями
                x = self.dropout(x)

        return x