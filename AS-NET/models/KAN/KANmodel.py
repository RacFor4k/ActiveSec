import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Dict, Optional, Union, Tuple, Any
import warnings
# import KAN.test.torchKAN

class KANAutoEncoder(nn.Module):
    """
    Гибкий автоэнкодер для восстановления файлов с поддержкой:
    - Точечной замены слоёв на KAN-свертки
    - Индивидуальных параметров для каждого KAN-слоя
    - Опционального пулинга (не рекомендуется для 1D)
    - Явного указания затёртых позиций
    """

    def __init__(
        self,
        vocab_size: int = 256,
        embed_dim: int = 64,
        layer_configs: List[Dict[str, Any]] = None,
        use_batch_norm: bool = True,
        use_skip_connections: bool = True,
        dropout_rate: float = 0.1,
        use_pool: bool = False,
        pool_config: Optional[List[int]] = None,
        base_activation = nn.GELU,
        kan_import_path: str = ".torchKAN"
    ):
        """
        Args:
            seq_len: Длина последовательности (1024)
            vocab_size: Размер "словаря" (256 для байтов)
            embed_dim: Размерность эмбеддингов
            layer_configs: Конфигурация слоёв. Пример:
                [
                    # Формат: {
                    #   'out_channels': int,
                    #   'kernel_size': int,
                    #   'layer_type': 'conv' | 'kan',
                    #   'kan_params': dict (опционально, только для layer_type='kan')
                    # }
                    {'out_channels': 64, 'kernel_size': 5, 'layer_type': 'conv'},
                    {'out_channels': 128, 'kernel_size': 5, 'layer_type': 'kan', 
                     'kan_params': {'grid_size': 5, 'spline_order': 3, 'scale_noise': 0.1}},
                    {'out_channels': 256, 'kernel_size': 5, 'layer_type': 'kan',
                     'kan_params': {'grid_size': 4, 'spline_order': 2}},
                    {'out_channels': 128, 'kernel_size': 5, 'layer_type': 'conv'},
                    {'out_channels': 64, 'kernel_size': 5, 'layer_type': 'conv'}
                ]
            use_batch_norm: Использовать BatchNorm1d
            use_skip_connections: Использовать skip-connections (U-Net)
            dropout_rate: Вероятность dropout
            use_pool: Использовать пулинг (не рекомендуется для 1D восстановления!)
            pool_config: Размеры пулинга для каждого слоя. Пример: [1, 2, 1, 2, 1]
            base_activation: Базовая функция активации (например, nn.GELU или nn.ReLU)
            kan_import_path: Путь для импорта KAN-слоёв (для изоляции зависимостей)
        """
        super().__init__()
        
        # Загрузка KAN модулей по требованию
        self.kan_import_path = kan_import_path
        self._load_kan_modules()
        
        # Валидация конфигурации
        if layer_configs is None:
            # Конфигурация по умолчанию (без KAN)
            layer_configs = [
                {'out_channels': 64, 'kernel_size': 5, 'layer_type': 'conv'},
                {'out_channels': 128, 'kernel_size': 5, 'layer_type': 'conv'},
                {'out_channels': 256, 'kernel_size': 5, 'layer_type': 'conv'},
                {'out_channels': 128, 'kernel_size': 5, 'layer_type': 'conv'},
                {'out_channels': 64, 'kernel_size': 5, 'layer_type': 'conv'}
            ]
            warnings.warn("Используется конфигурация по умолчанию без KAN-слоёв")
        
        assert len(layer_configs) % 2 == 1, "Число слоёв должно быть нечётным для симметричной архитектуры"
        if use_pool:
            assert pool_config is not None and len(pool_config) == len(layer_configs), \
                "pool_config должен быть указан и совпадать по длине с layer_configs"
            warnings.warn("⚠️ Пулинг в 1D задачах восстановления данных может ухудшить качество!")

        self.vocab_size = vocab_size
        self.use_pool = use_pool
        self.use_skip_connections = use_skip_connections
        self.num_layers = len(layer_configs)
        self.mid_idx = self.num_layers // 2
        self.base_activation = base_activation()
        
        # Эмбеддинги
        self.byte_embedding = nn.Embedding(vocab_size, embed_dim)
        self.mask_embedding = nn.Embedding(2, embed_dim)  # 0=нетронутый, 1=затёртый
        
        # Слои энкодера/декодера
        self.encoder_layers = nn.ModuleList()
        self.decoder_layers = nn.ModuleList()
        
        # BatchNorm, Dropout и пулинг
        self.encoder_bn = nn.ModuleList() if use_batch_norm else None
        self.decoder_bn = nn.ModuleList() if use_batch_norm else None
        self.encoder_dropout = nn.ModuleList()
        self.decoder_dropout = nn.ModuleList()
        
        if use_pool:
            self.encoder_pool = nn.ModuleList()
            self.decoder_unpool = nn.ModuleList()
            for i, pool_size in enumerate(pool_config):
                if pool_size > 1:
                    self.encoder_pool.append(nn.MaxPool1d(pool_size, return_indices=True))
                    self.decoder_unpool.append(nn.MaxUnpool1d(pool_size))
                else:
                    self.encoder_pool.append(None)
                    self.decoder_unpool.append(None)
        
        # Skip-connections проекции
        self.skip_projections = nn.ModuleList()
        
        # === Строим энкодер и декодер ===
        in_channels = embed_dim
        
        # Энкодер (включая bottleneck)
        for i in range(self.mid_idx + 1):
            config = layer_configs[i]
            out_channels = config['out_channels']
            kernel_size = config['kernel_size']
            padding = kernel_size // 2
            
            # Создаём слой в зависимости от типа
            layer = self._create_layer(
                in_channels, 
                out_channels, 
                kernel_size, 
                padding,
                config
            )
            self.encoder_layers.append(layer)
            
            # BatchNorm и Dropout
            if use_batch_norm:
                self.encoder_bn.append(nn.BatchNorm1d(out_channels))
            self.encoder_dropout.append(nn.Dropout1d(dropout_rate) if dropout_rate > 0 else nn.Identity())
            
            in_channels = out_channels
        
        # Декодер
        for i in range(self.mid_idx + 1, self.num_layers):
            config = layer_configs[i]
            out_channels = config['out_channels']
            kernel_size = config['kernel_size']
            padding = kernel_size // 2
            
            # Входные каналы для декодера = выходные каналы предыдущего слоя
            if i == self.mid_idx + 1:
                in_channels = layer_configs[self.mid_idx]['out_channels']
            
            # Проекция для skip-connection
            skip_in_channels = layer_configs[self.num_layers - 1 - i]['out_channels']
            if skip_in_channels != out_channels:
                self.skip_projections.append(
                    nn.Conv1d(skip_in_channels, out_channels, kernel_size=1)
                )
            else:
                self.skip_projections.append(nn.Identity())
            
            # Создаём слой декодера
            layer = self._create_layer(
                in_channels, 
                out_channels, 
                kernel_size, 
                padding,
                config
            )
            self.decoder_layers.append(layer)
            
            if use_batch_norm:
                self.decoder_bn.append(nn.BatchNorm1d(out_channels))
            self.decoder_dropout.append(nn.Dropout1d(dropout_rate) if dropout_rate > 0 else nn.Identity())
            
            in_channels = out_channels
        
        # Выходной слой
        self.output_layer = nn.Linear(layer_configs[-1]['out_channels'], vocab_size)

    def _load_kan_modules(self):
        """Загрузка KAN-модулей из локального файла"""
        try:
            # Импортируем KANConv1d из torchKAN.py в той же директории
            from .torchKAN import KANConv1d
            self.KANConv1d = KANConv1d
            self.kan_available = True
            print("✅ KANConv1d загружен успешно из локального модуля")
        except ImportError as e:
            self.kan_available = False
            warnings.warn(f"❌ Не удалось загрузить KAN-слои: {e}. Все слои будут обычными свёртками.")

    def _create_layer(self, in_channels, out_channels, kernel_size, padding, config):
        """Создаёт слой в зависимости от конфигурации"""
        layer_type = config.get('layer_type', 'conv')
        kan_params = config.get('kan_params', {})
        
        if layer_type == 'kan' and self.kan_available:
            # Создаём KAN-свёртку с индивидуальными параметрами
            return self.KANConv1d(
                in_channels,
                out_channels,
                kernel_size=kernel_size,
                padding=padding,
                **kan_params
            )
        else:
            if layer_type == 'kan' and not self.kan_available:
                warnings.warn(f"KANConv1d недоступен. Используется обычная свёртка вместо KAN-слоя.")
            # Стандартная свёртка
            return nn.Conv1d(
                in_channels,
                out_channels,
                kernel_size=kernel_size,
                padding=padding
            )

    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Тензор байтов (batch_size, seq_len), значения 0-255
            mask: Бинарная маска (batch_size, seq_len), 
                  где 1 = позиция была затёрта и требует восстановления
        Returns:
            logits: (batch_size, seq_len, vocab_size)
        """
        # === 1. Эмбеддинги с информацией о маске ===
        byte_emb = self.byte_embedding(x)  # (B, L, embed_dim)
        mask_emb = self.mask_embedding(mask.long())  # (B, L, embed_dim)
        x = byte_emb + mask_emb  # (B, L, embed_dim)
        x = x.permute(0, 2, 1)  # (B, embed_dim, L)

        # === 2. Энкодер ===
        encoder_outputs = []
        pool_indices = [] if self.use_pool else None

        for i in range(self.mid_idx + 1):
            # Сохраняем для skip-connection
            skip = x.clone()
            encoder_outputs.append(skip)
            
            # Свёртка
            x = self.encoder_layers[i](x)
            
            # Активация
            x = self.base_activation(x)
            
            # BatchNorm и Dropout
            if self.encoder_bn is not None:
                x = self.encoder_bn[i](x)
            x = self.encoder_dropout[i](x)
            
            # Пулинг
            if self.use_pool and self.encoder_pool[i] is not None:
                x, indices = self.encoder_pool[i](x)
                pool_indices.append(indices)

        # === 3. Декодер ===
        skip_idx = len(encoder_outputs) - 2  # Пропускаем bottleneck

        for i in range(len(self.decoder_layers)):
            # Unpooling
            if self.use_pool and self.decoder_unpool[i] is not None:
                unpool_idx = len(pool_indices) - 1 - i
                x = self.decoder_unpool[i](x, pool_indices[unpool_idx])
            
            # Свёртка декодера
            x = self.decoder_layers[i](x)
            
            # Skip-connection
            if self.use_skip_connections and skip_idx >= 0:
                skip_val = encoder_outputs[skip_idx]
                
                # Масштабируем если нужно
                if x.shape[-1] != skip_val.shape[-1]:
                    skip_val = F.interpolate(
                        skip_val, 
                        size=x.shape[-1], 
                        mode='linear', 
                        align_corners=False
                    )
                
                # Проекция каналов
                skip_val = self.skip_projections[i](skip_val)
                
                # Суммируем
                x = x + skip_val
                skip_idx -= 1
            
            # Активация
            x = self.base_activation(x)
            
            # BatchNorm и Dropout
            if self.decoder_bn is not None:
                bn_idx = i
                x = self.decoder_bn[bn_idx](x)
            x = self.decoder_dropout[i](x)

        # === 4. Выходной слой ===
        x = x.permute(0, 2, 1)  # (B, L, C)
        logits = self.output_layer(x)  # (B, L, vocab_size)
        return logits

    @torch.no_grad()
    def generate(
        self, 
        corrupted_bytes: torch.Tensor, 
        mask: torch.Tensor,
        temperature: float = 1.0,
        top_k: Optional[int] = None
    ) -> torch.Tensor:
        """Генерация восстановленных байтов с контролем качества"""
        self.eval()
        logits = self(corrupted_bytes, mask)
        
        # Температура и top-k фильтрация
        if temperature != 1.0:
            logits = logits / temperature
        
        if top_k is not None:
            top_k = min(top_k, logits.size(-1))
            indices_to_remove = logits < torch.topk(logits, top_k, dim=-1)[0][..., -1, None]
            logits[indices_to_remove] = -float('Inf')
        
        # Сэмплирование
        probs = F.softmax(logits, dim=-1)
        output_ids = torch.multinomial(probs.view(-1, probs.size(-1)), 1).view(probs.shape[:-1])
        
        # Восстанавливаем только затёртые позиции
        restored = corrupted_bytes.clone()
        restored[mask] = output_ids[mask]
        return restored

    def count_parameters(self, only_trainable: bool = False) -> int:
        """Подсчёт параметров модели с разбивкой по типам слоёв"""
        total = 0
        kan_params = 0
        conv_params = 0
        
        for name, param in self.named_parameters():
            if only_trainable and not param.requires_grad:
                continue
                
            param_count = param.numel()
            total += param_count
            
            if 'kan' in name.lower():
                kan_params += param_count
            elif 'conv' in name.lower() or 'output_layer' in name.lower():
                conv_params += param_count
        
        print(f"Параметры модели:")
        print(f"  Всего: {total:,}")
        print(f"  KAN-слои: {kan_params:,} ({kan_params/total:.1%})")
        print(f"  Обычные слои: {conv_params:,} ({conv_params/total:.1%})")
        return total
    
def extract_encoder_from_model(
    full_model: torch.nn.Module,
    return_bottleneck_only: bool = False
) -> torch.nn.Module:
    """
    Извлекает энкодер из полной модели FileRecoveryAutoEncoder
    
    Args:
        full_model: Полная модель FileRecoveryAutoEncoder
        return_bottleneck_only: Если True, возвращает только bottleneck представление,
                               если False, возвращает все промежуточные активации для skip-connections
    
    Returns:
        EncoderModule: Отдельный модуль энкодера
    """
    
    class EncoderModule(torch.nn.Module):
        def __init__(self, model, return_bottleneck_only):
            super().__init__()
            # Копируем необходимые компоненты
            self.byte_embedding = model.byte_embedding
            self.mask_embedding = model.mask_embedding
            self.encoder_layers = model.encoder_layers
            self.encoder_bn = model.encoder_bn
            self.encoder_dropout = model.encoder_dropout
            self.encoder_pool = getattr(model, 'encoder_pool', None)
            self.use_pool = model.use_pool
            self.mid_idx = model.mid_idx
            self.base_activation = model.base_activation
            self.return_bottleneck_only = return_bottleneck_only
            
        def forward(self, x: torch.Tensor, mask: torch.Tensor):
            """
            Args:
                x: (batch_size, seq_len) - байты
                mask: (batch_size, seq_len) - маска повреждений
                
            Returns:
                Если return_bottleneck_only=True:
                    bottleneck: (batch_size, channels, seq_len_reduced)
                Если return_bottleneck_only=False:
                    (bottleneck, encoder_outputs): где encoder_outputs - список промежуточных активаций
            """
            # Эмбеддинги
            byte_emb = self.byte_embedding(x)
            mask_emb = self.mask_embedding(mask.long())
            x = (byte_emb + mask_emb).permute(0, 2, 1)  # (B, embed_dim, L)
            
            encoder_outputs = []
            pool_indices = [] if self.use_pool else None
            
            # Проход по энкодеру
            for i in range(self.mid_idx + 1):
                skip = x.clone()
                encoder_outputs.append(skip)
                
                x = self.encoder_layers[i](x)
                x = self.base_activation(x)
                
                if self.encoder_bn is not None:
                    x = self.encoder_bn[i](x)
                x = self.encoder_dropout[i](x)
                
                if self.use_pool and self.encoder_pool[i] is not None:
                    x, indices = self.encoder_pool[i](x)
                    pool_indices.append(indices)
            
            if self.return_bottleneck_only:
                return x
            else:
                return x, encoder_outputs
    
    return EncoderModule(full_model, return_bottleneck_only)
