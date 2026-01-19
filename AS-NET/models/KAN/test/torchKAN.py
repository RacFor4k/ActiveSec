import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class KANLinear(nn.Module):
    """
    Полносвязный слой (FC) на архитектуре KAN.
    Оптимизированная версия:
    1. Удален неиспользуемый spline_scaler.
    2. Добавлен eps для защиты от NaN.
    3. Оптимизирован расчет сплайнов.
    """
    def __init__(
        self,
        in_features,
        out_features,
        grid_size=5,
        spline_order=3,
        scale_noise=0.1,
        scale_base=1.0,
        scale_spline=1.0,
        base_activation=torch.nn.SiLU,
        grid_eps=0.02,
        grid_range=[-1, 1],
    ):
        super(KANLinear, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.grid_size = grid_size
        self.spline_order = spline_order

        # Параметры сетки
        h = (grid_range[1] - grid_range[0]) / grid_size
        grid = (
            (
                torch.arange(-spline_order, grid_size + spline_order + 1) * h
                + grid_range[0]
            )
            .expand(in_features, -1)
            .contiguous()
        )
        self.register_buffer("grid", grid)

        # 1. Базовые веса (w_b): аналог линейного слоя с активацией
        self.base_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        
        # 2. Веса сплайнов (w_s): коэффициенты для B-сплайнов
        self.spline_weight = nn.Parameter(
            torch.Tensor(out_features, in_features, grid_size + spline_order)
        )

        self.scale_noise = scale_noise
        self.scale_base = scale_base
        self.scale_spline = scale_spline
        self.base_activation = base_activation()
        self.grid_eps = grid_eps

        self.reset_parameters()

    def reset_parameters(self):
        # Инициализация базовой части (Kaiming Uniform)
        nn.init.kaiming_uniform_(self.base_weight, a=math.sqrt(5) * self.scale_base)
        
        with torch.no_grad():
            # Инициализация сплайнов шумом
            # Это помогает нарушить симметрию, но держит значения близкими к нулю
            noise = (
                (
                    torch.rand(self.grid_size + 1, self.in_features, self.out_features)
                    - 1 / 2
                )
                * self.scale_noise
                / self.grid_size
            )
            
            # Инициализируем сплайны очень маленькими значениями.
            # В начале обучения сеть работает почти как MLP (только base_weight),
            # сплайны подключаются постепенно.
            self.spline_weight.data.copy_(
                (self.scale_spline * 0.01) * torch.randn_like(self.spline_weight)
            )

    def b_splines(self, x: torch.Tensor):
        """
        Вычисление B-сплайнов с защитой от NaN.
        """
        assert x.dim() == 2 and x.size(1) == self.in_features

        grid: torch.Tensor = self.grid
        x = x.unsqueeze(-1)
        
        # Базис 0-го порядка (ступеньки)
        bases = ((x >= grid[:, :-1]) & (x < grid[:, 1:])).to(x.dtype)
        
        # Берем eps из типа данных (1e-7 для float32, 6e-5 для float16)
        eps = torch.finfo(x.dtype).eps
        
        for k in range(1, self.spline_order + 1):
            # Расчет интервалов
            left_denom = grid[:, k:-1] - grid[:, : -(k + 1)]
            right_denom = grid[:, k + 1 :] - grid[:, 1:(-k)]
            
            # Рекурсивная формула с защитой от деления на 0
            term1 = (x - grid[:, : -(k + 1)]) / (left_denom + eps) * bases[:, :, :-1]
            term2 = (grid[:, k + 1 :] - x) / (right_denom + eps) * bases[:, :, 1:]
            
            bases = term1 + term2

        return bases

    def forward(self, x):
        # x shape: (batch, in_features)
        
        # 1. Базовая ветка: Linear(SiLU(x))
        # Обеспечивает стабильный поток градиентов
        base_output = F.linear(self.base_activation(x), self.base_weight)
        
        # 2. Сплайновая ветка
        spline_basis = self.b_splines(x) # (batch, in_features, spline_dim)
        
        # Эффективное вычисление суммы сплайнов через матричное умножение
        # Flattening: (batch, in_features * spline_dim)
        # Weight flattening: (out_features, in_features * spline_dim)
        spline_output = F.linear(
            spline_basis.view(x.size(0), -1),
            self.spline_weight.view(self.out_features, -1)
        )
        
        return base_output + spline_output
    

def compute_b_splines_for_conv(x: torch.Tensor, grid, spline_order):
    """
    Вспомогательная функция для сверток.
    x: (batch, in_channels, time/height, width...)
    grid: (in_channels, grid_points)
    """
    # Перемещаем каналы в конец для бродкастинга с сеткой: (B, ..., C)
    spatial_dims = x.shape[2:]
    x = x.permute(0, *range(2, x.dim()), 1) 
    x = x.unsqueeze(-1) # (B, ..., C, 1)
    
    # Расчет сплайнов (аналогично KANLinear, но с поддержкой лишних измерений)
    bases = ((x >= grid[:, :-1]) & (x < grid[:, 1:])).to(x.dtype)
    
    for k in range(1, spline_order + 1):
        left_intervals = grid[:, k:-1] - grid[:, : -(k + 1)]
        right_intervals = grid[:, k + 1 :] - grid[:, 1:(-k)]
        
        bases = (
            (x - grid[:, : -(k + 1)]) / left_intervals * bases[..., :-1]
        ) + (
            (grid[:, k + 1 :] - x) / right_intervals * bases[..., 1:]
        )
    
    # bases shape: (B, ..., C, spline_dim)
    # Нам нужно вернуть каналы на место и объединить C * spline_dim
    # (B, ..., C, spline_dim) -> (B, C, spline_dim, ...)
    bases = bases.permute(0, -2, -1, *range(1, x.dim()-2))
    
    return bases

class KANConv1d(nn.Module):
    def __init__(
        self,
        in_channels,
        out_channels,
        kernel_size,
        stride=1,
        padding=0,
        dilation=1,
        groups=1,
        bias=True,
        grid_size=5,
        spline_order=3,
        scale_noise=0.1,
        scale_base=1.0,
        scale_spline=1.0,
        base_activation=torch.nn.SiLU,
        grid_eps=0.02,
        grid_range=[-1, 1],
    ):
        super(KANConv1d, self).__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self.dilation = dilation
        self.groups = groups
        self.grid_size = grid_size
        self.spline_order = spline_order

        # Сетка (Grid) для каждого входного канала
        h = (grid_range[1] - grid_range[0]) / grid_size
        grid = (
            (
                torch.arange(-spline_order, grid_size + spline_order + 1) * h
                + grid_range[0]
            )
            .expand(in_channels, -1)
            .contiguous()
        )
        self.register_buffer("grid", grid)

        # 1. Base Conv: Обычная свертка над SiLU(x)
        self.base_conv = nn.Conv1d(
            in_channels, out_channels, kernel_size, stride, padding, dilation, groups, bias=bias
        )

        # 2. Spline Conv: Свертка над сплайнами
        # Входных каналов становится больше в (grid_size + spline_order) раз
        self.spline_dim = grid_size + spline_order
        self.spline_conv = nn.Conv1d(
            in_channels * self.spline_dim,
            out_channels,
            kernel_size,
            stride,
            padding,
            dilation,
            groups,
            bias=False # Bias уже есть в base_conv
        )

        self.base_activation = base_activation()
        self.scale_noise = scale_noise
        self.scale_base = scale_base
        self.scale_spline = scale_spline
        
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.kaiming_uniform_(self.base_conv.weight, a=math.sqrt(5) * self.scale_base)
        if self.base_conv.bias is not None:
            nn.init.zeros_(self.base_conv.bias)

        # Инициализация сплайнов (маленькие значения)
        nn.init.kaiming_uniform_(self.spline_conv.weight, a=math.sqrt(5) * self.scale_spline)
        with torch.no_grad():
            self.spline_conv.weight.data *= 0.01 * self.scale_spline

    def forward(self, x):
        # x: (batch, in_channels, length)
        
        # Ветка 1: Base
        base_out = self.base_conv(self.base_activation(x))
        
        # Ветка 2: Spline
        # (batch, in_channels, length) -> (batch, in_channels, spline_dim, length)
        spline_basis = compute_b_splines_for_conv(x, self.grid, self.spline_order)
        
        # Объединяем измерения каналов и сплайнов для подачи в Conv1d
        # (batch, in * spline_dim, length)
        batch, _, _, length = spline_basis.shape
        spline_basis = spline_basis.reshape(batch, self.in_channels * self.spline_dim, length)
        
        spline_out = self.spline_conv(spline_basis)
        
        return base_out + spline_out


class KANConv2d(nn.Module):
    def __init__(
        self,
        in_channels,
        out_channels,
        kernel_size,
        stride=1,
        padding=0,
        dilation=1,
        groups=1,
        bias=True,
        grid_size=5,
        spline_order=3,
        scale_noise=0.1,
        scale_base=1.0,
        scale_spline=1.0,
        base_activation=torch.nn.SiLU,
        grid_eps=0.02,
        grid_range=[-1, 1],
    ):
        super(KANConv2d, self).__init__()
        
        if isinstance(kernel_size, int):
            kernel_size = (kernel_size, kernel_size)
            
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self.dilation = dilation
        self.groups = groups
        self.grid_size = grid_size
        self.spline_order = spline_order

        # Сетка
        h = (grid_range[1] - grid_range[0]) / grid_size
        grid = (
            (
                torch.arange(-spline_order, grid_size + spline_order + 1) * h
                + grid_range[0]
            )
            .expand(in_channels, -1)
            .contiguous()
        )
        self.register_buffer("grid", grid)

        # Base Conv
        self.base_conv = nn.Conv2d(
            in_channels, out_channels, kernel_size, stride, padding, dilation, groups, bias=bias
        )

        # Spline Conv
        self.spline_dim = grid_size + spline_order
        self.spline_conv = nn.Conv2d(
            in_channels * self.spline_dim,
            out_channels,
            kernel_size,
            stride,
            padding,
            dilation,
            groups,
            bias=False
        )

        self.base_activation = base_activation()
        self.scale_noise = scale_noise
        self.scale_base = scale_base
        self.scale_spline = scale_spline
        
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.kaiming_uniform_(self.base_conv.weight, a=math.sqrt(5) * self.scale_base)
        if self.base_conv.bias is not None:
            nn.init.zeros_(self.base_conv.bias)

        nn.init.kaiming_uniform_(self.spline_conv.weight, a=math.sqrt(5) * self.scale_spline)
        with torch.no_grad():
            self.spline_conv.weight.data *= 0.01 * self.scale_spline

    def forward(self, x):
        # x: (batch, in_channels, H, W)
        
        # Ветка 1: Base
        base_out = self.base_conv(self.base_activation(x))
        
        # Ветка 2: Spline
        # (batch, in_channels, spline_dim, H, W)
        spline_basis = compute_b_splines_for_conv(x, self.grid, self.spline_order)
        
        # Flatten каналов и сплайнов
        batch, _, _, H, W = spline_basis.shape
        spline_basis = spline_basis.reshape(batch, self.in_channels * self.spline_dim, H, W)
        
        spline_out = self.spline_conv(spline_basis)
        
        return base_out + spline_out
    
def count_prunable_kan_connections(model: nn.Module, threshold: float = 1e-2):
    """
    Анализирует модель и считает количество связей, которые можно отсечь или упростить.
    
    Args:
        model: PyTorch модель.
        threshold: Пороговое значение (абсолютное). Если веса меньше этого значения, 
                   считаем их неактивными.
                   
    Returns:
        dict: Статистика по всей модели и по каждому слою.
    """
    results = {
        "total_connections": 0,       # Всего связей (вход -> выход)
        "spline_inactive": 0,         # Связи, где сплайны ~ 0 (можно заменить на Linear)
        "fully_prunable": 0,          # Связи, где и сплайны, и base ~ 0 (можно удалить)
        "layers": {}                  # Детализация по слоям
    }
    
    print(f"Анализ модели с порогом {threshold}...\n")

    for name, module in model.named_modules():
        # 1. Анализ KANLinear
        if isinstance(module, KANLinear):
            # spline_weight: (out, in, grid_size + order)
            # base_weight: (out, in)
            
            # Максимальное абсолютное значение коэффициентов сплайна для каждой связи
            # (out, in)
            max_spline_coeffs = module.spline_weight.abs().max(dim=-1).values
            
            # Абсолютное значение базового веса
            abs_base_weight = module.base_weight.abs()
            
            # Считаем
            total = max_spline_coeffs.numel()
            
            # Маска: где сплайны "мертвые"
            spline_mask = max_spline_coeffs < threshold
            
            # Маска: где и сплайны, и база "мертвые"
            prunable_mask = spline_mask & (abs_base_weight < threshold)
            
            s_inactive = spline_mask.sum().item()
            f_prunable = prunable_mask.sum().item()
            
            results["total_connections"] += total
            results["spline_inactive"] += s_inactive
            results["fully_prunable"] += f_prunable
            
            results["layers"][name] = {
                "type": "KANLinear",
                "total": total,
                "spline_inactive": s_inactive,
                "fully_prunable": f_prunable,
                "ratio_spline": s_inactive / total,
                "ratio_prunable": f_prunable / total
            }

        # 2. Анализ KANConv2d (Оптимизированная версия)
        elif isinstance(module, KANConv2d):
            # spline_conv.weight: (out, in * spline_dim, kH, kW)
            # base_conv.weight: (out, in, kH, kW)
            
            out_c, in_c = module.out_channels, module.in_channels
            spline_dim = module.spline_dim
            
            # --- Анализ сплайнов ---
            w_s = module.spline_conv.weight
            # Решейпим, чтобы отделить входные каналы от сплайнов
            # (out, in, spline_dim, kH, kW)
            w_s_reshaped = w_s.view(out_c, in_c, spline_dim, *module.kernel_size)
            
            # Находим макс. коэффициент сплайна по всему ядру и всем коэффициентам сетки
            # Результат: матрица (out, in) - сила сплайновой связи между каналами
            # dim=(2,3,4) -> max over (spline_dim, kH, kW)
            max_spline_coeffs = w_s_reshaped.abs().amax(dim=(2, 3, 4))
            
            # --- Анализ базы ---
            w_b = module.base_conv.weight # (out, in, kH, kW)
            # Макс вес в ядре свертки
            max_base_weight = w_b.abs().amax(dim=(2, 3))
            
            # Считаем
            total = out_c * in_c
            spline_mask = max_spline_coeffs < threshold
            prunable_mask = spline_mask & (max_base_weight < threshold)
            
            s_inactive = spline_mask.sum().item()
            f_prunable = prunable_mask.sum().item()
            
            results["total_connections"] += total
            results["spline_inactive"] += s_inactive
            results["fully_prunable"] += f_prunable
            
            results["layers"][name] = {
                "type": "KANConv2d",
                "total": total,
                "spline_inactive": s_inactive,
                "fully_prunable": f_prunable,
                "ratio_spline": s_inactive / total,
                "ratio_prunable": f_prunable / total
            }

        # 3. Анализ KANConv1d (Оптимизированная версия)
        elif isinstance(module, KANConv1d):
            out_c, in_c = module.out_channels, module.in_channels
            spline_dim = module.spline_dim
            
            # spline_conv.weight: (out, in * spline_dim, k)
            w_s = module.spline_conv.weight
            w_s_reshaped = w_s.view(out_c, in_c, spline_dim, module.kernel_size[0])
            
            # Max over (spline_dim, k)
            max_spline_coeffs = w_s_reshaped.abs().amax(dim=(2, 3))
            
            w_b = module.base_conv.weight
            max_base_weight = w_b.abs().amax(dim=2)
            
            total = out_c * in_c
            spline_mask = max_spline_coeffs < threshold
            prunable_mask = spline_mask & (max_base_weight < threshold)
            
            s_inactive = spline_mask.sum().item()
            f_prunable = prunable_mask.sum().item()
            
            results["total_connections"] += total
            results["spline_inactive"] += s_inactive
            results["fully_prunable"] += f_prunable
            
            results["layers"][name] = {
                "type": "KANConv1d",
                "total": total,
                "spline_inactive": s_inactive,
                "fully_prunable": f_prunable,
                "ratio_spline": s_inactive / total,
                "ratio_prunable": f_prunable / total
            }

    # Вывод сводной информации
    print(f"--- Результаты анализа (Threshold: {threshold}) ---")
    print(f"Всего связей: {results['total_connections']}")
    print(f"Сплайны неактивны (можно линеаризовать): {results['spline_inactive']} ({results['spline_inactive']/results['total_connections']:.1%})")
    print(f"Связь полностью неактивна (можно удалить): {results['fully_prunable']} ({results['fully_prunable']/results['total_connections']:.1%})")
    
    return results