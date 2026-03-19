"""Model definitions for Mars weather prediction."""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset


class MarsWeatherDataset(Dataset):
    """Sliding window dataset for LSTM training."""

    def __init__(self, df, feature_cols, targets, seq_len=30, horizon=1):
        self.features = df[feature_cols].values.astype(np.float32)
        self.targets = df[targets].values.astype(np.float32)
        self.seq_len = seq_len
        self.horizon = horizon
        n = len(self.features) - self.seq_len - self.horizon + 1
        if n <= 0:
            raise ValueError(
                f"Dataset too small: {len(self.features)} rows for "
                f"seq_len={seq_len} + horizon={horizon} (need at least {seq_len + horizon})"
            )

    def __len__(self):
        return max(0, len(self.features) - self.seq_len - self.horizon + 1)

    def __getitem__(self, idx):
        x = self.features[idx : idx + self.seq_len]
        y = self.targets[idx + self.seq_len + self.horizon - 1]
        return torch.tensor(x), torch.tensor(y)


class LSTMPredictor(nn.Module):
    """2-layer LSTM for multi-output weather prediction."""

    def __init__(self, input_size, hidden_size=64, num_layers=2, output_size=5, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        # x: (batch, seq_len, features)
        lstm_out, _ = self.lstm(x)
        last = lstm_out[:, -1, :]  # take last timestep
        out = self.fc(self.dropout(last))
        return out


class SeasonalBaseline:
    """Simple seasonal baseline: predict based on same sol_in_year from training data.

    For each target, averages the training values at the same position in the Martian year.
    """

    def __init__(self, targets, period=668):
        self.targets = targets
        self.period = period
        self.seasonal_means = {}

    def fit(self, df):
        """Compute seasonal means from training data."""
        df = df.copy()
        df["_pos"] = df["sol"] % self.period
        for target in self.targets:
            self.seasonal_means[target] = df.groupby("_pos")[target].mean().to_dict()
        return self

    def predict(self, sols):
        """Predict targets for given sol numbers."""
        results = {}
        for target in self.targets:
            means = self.seasonal_means[target]
            results[target] = [means.get(s % self.period, np.nan) for s in sols]
        return results
