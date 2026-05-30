import torch
import torch.nn as nn
import torch.nn.functional as F

class TabCNN(nn.Module):
    def __init__(self):
        super().__init__()

        # =========================
        # CNN (feature extractor)
        # =========================
        self.conv1 = nn.Conv2d(4, 32, kernel_size=(9,3), padding=(4,1))
        self.conv2 = nn.Conv2d(32, 64, kernel_size=(5,3), padding=(2,1))
        self.conv3 = nn.Conv2d(64, 128, kernel_size=(3,3), padding=(1,1))
        self.conv4 = nn.Conv2d(128,128, kernel_size=(3,3), padding=(1,1))

        self.bn1 = nn.BatchNorm2d(32)
        self.bn2 = nn.BatchNorm2d(64)
        self.bn3 = nn.BatchNorm2d(128)
        self.bn4 = nn.BatchNorm2d(128)

        self.pool = nn.MaxPool2d(kernel_size=(1,2), stride=(1,2))

        # 🔥 NEW: CNN regularization
        self.dropout_cnn = nn.Dropout2d(0.1)

        # =========================
        # GRU (temporal modeling)
        # =========================
        self.gru = nn.GRU(
            input_size=256,     # mean + max pooling concat
            hidden_size=160,    # 🔥 increased from 128
            num_layers=1,
            batch_first=True,
            bidirectional=True
        )

        # 🔥 NEW: GRU regularization
        self.dropout_gru = nn.Dropout(0.2)

        # =========================
        # Attention (fixed, optional)
        # =========================
        self.attention = nn.Sequential(
            nn.Linear(320, 128),   # 160*2 = 320
            nn.Tanh(),
            nn.Linear(128, 1)      # 🔥 fixed (was 96 bug)
        )

        # =========================
        # Dense layers
        # =========================
        self.fc1 = nn.Linear(320, 128)  # 🔥 updated input size
        self.fc2 = nn.Linear(128, 128)

        self.dropout = nn.Dropout(0.35)

        # 🔥 NEW: stabilization
        self.norm = nn.LayerNorm(128)

        # =========================
        # Heads
        # =========================
        self.note_heads = nn.Linear(128, 64)
        self.string_heads = nn.Linear(128, 6)

    def forward(self, x):

        # =========================
        # CNN
        # =========================
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.pool(x)
        x = self.dropout_cnn(x)

        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = self.dropout_cnn(x)

        x = F.relu(self.bn4(self.conv4(x)))

        # =========================
        # Collapse frequency
        # =========================
        x = torch.cat([
            torch.mean(x, dim=3),
            torch.max(x, dim=3).values
        ], dim=1)  # (B, C, T)

        x = x.permute(0, 2, 1)  # (B, T, C)

        # =========================
        # GRU
        # =========================
        x, _ = self.gru(x)
        x = self.dropout_gru(x)

        attn_weights = torch.softmax(self.attention(x), dim=1)  # (B,T,1)
        x = torch.sum(x * attn_weights, dim=1)

        # =========================
        # Dense
        # =========================
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = self.norm(x)

        # =========================
        # Heads
        # =========================
        note_out = self.note_heads(x)
        string_out = self.string_heads(x)

        return note_out, string_out