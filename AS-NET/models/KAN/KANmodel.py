import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from .test.torchKAN import KANLinear, KANConv1d


class KANAutoEncoder(nn.Module):
    """
    Автоэнкодерная модель с использованием KAN свёрток для кодирования и декодирования

    Args:
        architecture: список кортежей (channels, use_kan, kernel_size) определяющий архитектуру модели
                     Формат: [(channels, use_kan, kernel_size), ...]
                     Пример: [[32,0,3],[128,1,3],[258,1,3],[128,1,3],[32,0,3]]
        vocab_size: int - размер словаря (по умолчанию 256 для байтовых значений 0-255)
        embedding_dim: int - размерность эмбеддинга (по умолчанию 64)
        use_batch_norm: bool - использовать ли батч-нормализацию (по умолчанию True)
        use_skip_connections: bool - использовать ли skip соединения (по умолчанию True)
    """

    def __init__(self, architecture=[[32,0,3],[128,1,3],[258,1,3],[128,1,3],[32,0,3]],
                 vocab_size=256, embedding_dim=64, use_batch_norm=True, use_skip_connections=True):
        super(KANAutoEncoder, self).__init__()

        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.use_batch_norm = use_batch_norm
        self.use_skip_connections = use_skip_connections

        # Слой эмбеддинга для преобразования бинарного ввода в плотные векторы
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # Определяем архитектуру энкодера и декодера
        mid_idx = len(architecture) // 2 + 1
        encoder_arch = architecture[:mid_idx]
        decoder_arch = architecture[mid_idx-1:]  # Включаем средний слой в обе части

        self.enc_layers, self.enc_bn, self.enc_skip = self._build_network(encoder_arch, embedding_dim, is_encoder=True)
        self.dec_layers, self.dec_bn, self.dec_skip = self._build_network(decoder_arch, embedding_dim, is_encoder=False)

        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.output_layer = nn.Linear(architecture[-1][0], vocab_size)

        # Выходной слой для отображения обратно в размер словаря
        self.output_layer = nn.Linear(architecture[-1][0], vocab_size)

        # Инициализация весов
        self._initialize_weights()

    def _build_network(self, architecture, embedding_dim, is_encoder=True):
        """
        Создаёт сеть энкодера или декодера на основе архитектуры
        """
        layers = nn.ModuleList()
        bn_layers = nn.ModuleList()
        skip_connections = nn.ModuleList()

        # Определяем входные/выходные каналы в зависимости от направления
        if is_encoder:
            in_channels = embedding_dim
            layer_configs = architecture
        else:
            # Для декодера обращаем архитектуру
            reversed_arch = architecture[::-1]
            # Меняем местами вход/выход для декодера
            in_channels = reversed_arch[0][0]  # Начинаем с каналов последнего слоя
            layer_configs = reversed_arch[1:]  # Пропускаем первый, так как он обрабатывается отдельно

        for i, (out_channels, use_kan, kernel_size) in enumerate(layer_configs):
            # Вычисляем padding для сохранения размерности
            padding = kernel_size // 2

            if use_kan == 1:
                # Используем KAN свертку
                conv_layer = KANConv1d(
                    in_channels=in_channels,
                    out_channels=out_channels,
                    kernel_size=kernel_size,
                    padding=padding,
                    stride=1
                )
            else:
                # Используем стандартную свертку
                conv_layer = nn.Conv1d(
                    in_channels=in_channels,
                    out_channels=out_channels,
                    kernel_size=kernel_size,
                    padding=padding,
                    stride=1
                )

            layers.append(conv_layer)

            # Добавляем батч-нормализацию если включена
            if self.use_batch_norm and bn_layers is not None:
                bn_layer = nn.BatchNorm1d(out_channels)
                bn_layers.append(bn_layer)

            # Добавляем skip connection если включена
            if self.use_skip_connections and skip_connections is not None:
                # Если размеры совпадают, используем identity, иначе линейное преобразование
                if in_channels != out_channels:
                    skip_conn = nn.Conv1d(in_channels, out_channels, kernel_size=1)
                else:
                    skip_conn = nn.Identity()
                skip_connections.append(skip_conn)

            in_channels = out_channels

        return layers, bn_layers, skip_connections

    def encode(self, x):
        """
        Кодирование входа в латентное представление
        """
        # x форма: (batch_size, sequence_length)
        embedded = self.embedding(x)  # (batch_size, sequence_length, embedding_dim)

        # Транспонируем для сверточных слоев: (batch_size, embedding_dim, sequence_length)
        x_encoded = embedded.transpose(1, 2)

        # Сохраняем промежуточные результаты для skip соединений
        encoded_outputs = []

        # Применяем слои энкодера
        prev_x = x_encoded
        for i, layer in enumerate(self.enc_layers):
            x_encoded = layer(x_encoded)

            if self.use_skip_connections and len(self.enc_skip) > 0:
                skip_conn = self.enc_skip[i]
                x_encoded = x_encoded + skip_conn(prev_x)
                prev_x = x_encoded

            x_encoded = F.gelu(x_encoded)

            if self.use_batch_norm and len(self.enc_bn) > 0:
                x_encoded = self.enc_bn[i](x_encoded)

            encoded_outputs.append(x_encoded)

        return x_encoded, encoded_outputs

    def decode(self, x_encoded, encoded_outputs=None):
        """
        Декодирование латентного представления обратно в исходное пространство
        """
        # Применяем слои декодера
        x_decoded = x_encoded
        num_decoder_layers = len(self.dec_layers)

        for i, layer in enumerate(self.dec_layers):
            x_decoded = layer(x_decoded)

            if i < num_decoder_layers - 1:
                if (self.use_skip_connections and 
                    len(self.dec_skip) > 0 and 
                    encoded_outputs is not None):
                    
                    skip_idx = len(encoded_outputs) - 1 - i
                    if skip_idx >= 0:
                        x_decoded = x_decoded + self.dec_skip[i](encoded_outputs[skip_idx])

                x_decoded = F.gelu(x_decoded)

                if self.use_batch_norm and len(self.dec_bn) > 0:
                    x_decoded = self.dec_bn[i](x_decoded)

        # Транспонируем обратно: (batch_size, sequence_length, channels)
        x_decoded = x_decoded.transpose(1, 2)

        # Применяем выходной слой для отображения в размер словаря
        # Изменяем форму на (-1, channels) для линейного слоя
        batch_size, seq_len, channels = x_decoded.shape
        x_decoded = x_decoded.contiguous().view(-1, channels)
        output = self.output_layer(x_decoded)

        # Изменяем форму обратно на (batch_size, sequence_length, vocab_size)
        output = output.view(batch_size, seq_len, self.vocab_size)

        return output

    def forward(self, x):
        """
        Прямой проход через энкодер и декодер
        """
        encoded, encoded_outputs = self.encode(x)
        decoded = self.decode(encoded, encoded_outputs)
        return decoded

    def get_encoder(self):
        """
        Возвращает только энкодерную часть модели для сохранения
        """
        encoder_only = nn.ModuleList()
        encoder_only.append(self.embedding)
        encoder_only.extend(self.enc_layers)  # Слои энкодера
        if self.use_batch_norm:
            encoder_only.extend(self.enc_bn)  # Батч-нормы энкодера
        if self.use_skip_connections:
            encoder_only.extend(self.enc_skip)  # Skip соединения энкодера

        return encoder_only

    def _initialize_weights(self):
        """Инициализация весов с использованием различных методов инициализации"""
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
