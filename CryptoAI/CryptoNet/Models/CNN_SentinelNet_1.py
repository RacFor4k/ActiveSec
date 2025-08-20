import math
import torch
import torch.nn as nn
import torch.nn.functional as F

def pad_and_mask(buffer: bytes, max_len=10240, pad_idx=256):
    """
    buffer: bytes или список байтов (0..255)
    max_len: фиксированная длина последовательности
    pad_idx: индекс для PAD
    
    return:
      byte_ids: LongTensor [max_len]
      mask: BoolTensor [max_len] (True = реальный байт, False = PAD)
    """
    # Преобразуем в список чисел (0..255)
    arr = list(buffer)
    length = min(len(arr), max_len)
    
    # Обрезаем, если слишком длинно
    arr = arr[:max_len]
    
    # Паддинг справа
    padded = arr + [pad_idx] * (max_len - length)
    
    # Маска: 1 для реальных байтов, 0 для паддинга
    mask = [1] * length + [0] * (max_len - length)
    
    return torch.tensor(padded, dtype=torch.long), torch.tensor(mask, dtype=torch.bool)

class AttnPool1D(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.q = nn.Parameter(torch.randn(1, 1, d_model) * 0.02)
        self.proj = nn.Linear(d_model, d_model, bias=False)

    def forward(self, x, mask=None):
        # x: [B, L, C], mask: [B, L] (True=keep, False=pad)
        q = self.q.expand(x.size(0), -1, -1)                      # [B,1,C]
        k = self.proj(x)                                          # [B,L,C]
        attn = torch.matmul(q, k.transpose(1, 2)) / math.sqrt(x.size(-1))  # [B,1,L]

        if mask is not None:
            # заменяем на -1e9 вместо -inf для стабильности экспорта
            attn = attn.masked_fill(mask.unsqueeze(1).logical_not(), -1e9)

        w = torch.softmax(attn, dim=-1)                           # [B,1,L]
        out = torch.bmm(w, x).squeeze(1)                          # [B,C]
        return out


class DWSeparableConv(nn.Module):
    def __init__(self, c, k, stride=1, dilation=1):
        super().__init__()
        padding = ((k - 1) // 2) * dilation
        self.dw = nn.Conv1d(c, c, k, stride=stride,
                            padding=padding, dilation=dilation, groups=c)
        self.pw = nn.Conv1d(c, c, 1)
        self.bn = nn.BatchNorm1d(c)

    def forward(self, x):
        x = self.pw(self.dw(x))
        return F.relu(self.bn(x))


class SentinelNet(nn.Module):
    def __init__(
        self,
        max_len=10240,         # фиксируем входную длину
        byte_vocab_size=257,   # 256 + PAD
        byte_dim=16,
        cnn_channels=192,
        type_vocab_size=32,
        type_dim=16,
        offset_dim=16,
        num_blocks=6,
        kernel_sizes=(5, 7, 9),
        dilations=(1, 2, 4, 8),
        stride_every=2,
        num_classes=2,
        emb_out_dim=128
    ):
        super().__init__()
        self.max_len = max_len
        self.byte_pad_idx = 256

        # Эмбеддинг байтов
        self.byte_emb = nn.Embedding(
            byte_vocab_size, byte_dim, padding_idx=self.byte_pad_idx
        )
        self.in_proj = nn.Conv1d(byte_dim, cnn_channels, 1)

        # CNN блоки
        blocks = []
        for i in range(num_blocks):
            k = kernel_sizes[i % len(kernel_sizes)]
            d = dilations[i % len(dilations)]
            s = 2 if (i % stride_every == stride_every - 1) else 1
            blocks.append(DWSeparableConv(cnn_channels, k, stride=s, dilation=d))
        self.cnn = nn.Sequential(*blocks)

        # Attention pooling
        self.attnpool = AttnPool1D(cnn_channels)

        # Метаданные
        self.type_emb = nn.Embedding(type_vocab_size, type_dim)
        self.offset_proj = nn.Sequential(
            nn.Linear(1, offset_dim),
            nn.ReLU()
        )

        # Классификационная голова
        fused_dim = cnn_channels + type_dim + offset_dim
        self.head = nn.Sequential(
            nn.Linear(fused_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, emb_out_dim),
            nn.ReLU()
        )
        self.cls = nn.Linear(emb_out_dim, num_classes)

    def forward(self, byte_ids, byte_mask, type_ids, offsets):
        """
        byte_ids: Long [B, MAX_LEN] (0..255, 256=PAD)
        byte_mask: Bool [B, MAX_LEN] (True=валидный байт, False=PAD)
        type_ids: Long [B]
        offsets:  Float [B]
        """
        # --- bytes ---
        x = self.byte_emb(byte_ids)          # [B,L,D]
        x = x.transpose(1, 2)                # [B,D,L]
        x = self.in_proj(x)                  # [B,C,L]
        x = self.cnn(x)                      # [B,C,L']
        x = x.transpose(1, 2)                # [B,L',C]

        # Маску подгоняем под уменьшенную длину
        if byte_mask is not None:
            L_out = x.size(1)
            step = self.max_len // L_out
            mask_ds = byte_mask[:, ::step][:, :L_out]
        else:
            mask_ds = None

        x_pool = self.attnpool(x, mask_ds)   # [B,C]

        # --- meta ---
        t = self.type_emb(type_ids)          # [B, type_dim]
        o = self.offset_proj(offsets.view(-1, 1))  # [B, offset_dim]

        h = torch.cat([x_pool, t, o], dim=-1)
        emb = self.head(h)                   # [B, emb_out_dim]
        logits = self.cls(emb)               # [B, 2]
        return logits, emb
