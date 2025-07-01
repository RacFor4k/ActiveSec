import torch
import torch.nn as nn

#позиционное форматирование (определяет признаки с учетом позиции в последовательности)
class LearnedPositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=256):
        super().__init__()
        self.pos_embedding = nn.Embedding(max_len, d_model)

    def forward(self, x):
        positions = torch.arange(0, x.size(1), device=x.device).unsqueeze(0)
        return x + self.pos_embedding(positions)

class NN(nn.Module):
    # 2 свертки, усменьшение размера в 2 раза, увеличение глубины в 4 раза
    class CNN(nn.Module):
        def __init__(self, num_classes, dropout):
            super().__init__()
            self.conv1 = nn.Conv1d(
                in_channels=num_classes,
                out_channels=num_classes * 2,
                kernel_size=3,
                padding=1
            )
            self.bn1 = nn.BatchNorm1d(num_classes * 2)
            self.conv2 = nn.Conv1d(
                in_channels=num_classes * 2,
                out_channels=num_classes * 4,
                kernel_size=3,
                padding=1
            )
            self.bn2 = nn.BatchNorm1d(num_classes * 4)
            self.relu = nn.ReLU()
            self.maxpool = nn.MaxPool1d(kernel_size=2, stride=2)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x):
            residual = x  # сохранение исходного входа
            x = x.transpose(1, 2)
            x = self.conv1(x)
            x = self.bn1(x)
            x = self.relu(x)
            x = self.maxpool(x)
            x = self.dropout(x)

            x = self.conv2(x)
            x = self.bn2(x)
            x = self.relu(x)
            x = self.dropout(x)
            x = x.transpose(1, 2)
            return x

    # Внимание с агрегацией и LayerNorm
    # x = (B, S, H) mask = (B, S)
    class AttentionPool(nn.Module):
        def __init__(self, d_model, dropout):
            super().__init__()
            self.attention = nn.Sequential(
                nn.Linear(d_model, d_model // 2),
                nn.Tanh(),
                nn.Linear(d_model // 2, 1)
            )
            self.norm = nn.LayerNorm(d_model)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x, mask=None):
            attn_scores = self.attention(x).squeeze(-1)  # [B, S]

            if mask is not None:
                attn_scores = attn_scores.masked_fill(mask, float('-inf'))

            attn_weights = torch.softmax(attn_scores, dim=1).unsqueeze(-1)  # [B, S, 1]
            pooled = torch.sum(attn_weights * x, dim=1)  # [B, H]
            pooled = self.norm(pooled)
            pooled = self.dropout(pooled)
            return pooled

    # Transformer + attention pool + классификация
    # x = (B, S, H) mask = (B, S)
    class Transforemer(nn.Module):
        def __init__(self, hidden_size, nhead, num_layers, max_len, dropout):
            super().__init__()
            self.max_len = max_len
            self.time_emb = LearnedPositionalEncoding(hidden_size, max_len=max_len)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=hidden_size,
                nhead=nhead,
                dropout=dropout,
                batch_first=False  # PyTorch default
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            self.pool = NN.AttentionPool(hidden_size, dropout=dropout)
            self.norm = nn.LayerNorm(hidden_size)
            self.dropout = nn.Dropout(dropout)

            self.decoder = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size // 2, 1),
                nn.Sigmoid()
            )

        def forward(self, x, mask=None):
            if mask is None:
                mask = self.get_mask(x)
            x = self.time_emb(x)               # [B, S, H]
            x = x.transpose(0, 1)              # [S, B, H]
            x = self.encoder(x, src_key_padding_mask=mask)
            x = x.transpose(0, 1)              # [B, S, H]
            x = self.pool(x, mask=mask)        # [B, H]
            x = self.norm(x)
            x = self.dropout(x)
            x = self.decoder(x)                # [B, 1]
            return x

        def get_mask(self, x):
            mask = []
            for item in x:
                seq_len = len(item)
                mask.append([False] * seq_len + [True] * (self.max_len - seq_len))
            return torch.BoolTensor(mask).to(x.device)

    def __init__(self, emb_dim=8, hidden_size=512, nhead=8, ts_layers=4, max_len=512, dropout = 0.1):
        super().__init__()
        
        # разбитие каждого байта на массив признаков
        self.emb = nn.Embedding(256, embedding_dim=emb_dim)

        # поиск локальных зависимостей через 2 свёртки + пуллинг (уменьшение размера в 2 раза)
        self.conv = NN.CNN(emb_dim, dropout)

        # сжатие свертки в глубину с (B, S, emb_dim*4) в (B, S)
        self.pooling = NN.AttentionPool(emb_dim * 4, dropout)
        self.relu = nn.ReLU()
        
        # поиск глобальных зависимостей и конечная классификация
        self.transformer = NN.Transforemer(
            hidden_size=hidden_size,
            nhead=nhead,
            num_layers=ts_layers,
            max_len=max_len // 2,
            dropout=dropout,
        )

    def forward(self, x):
        x = self.emb(x)        # [B, S, emb_dim]
        x = self.conv(x)       # [B, S//2, emb_dim*4]
        x = self.pooling(x)    # [B, emb_dim*4]
        x = self.relu(x)
        x = self.transformer(x)  # [B, 1]
        return x
