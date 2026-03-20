"""Mars Weather Prediction — ML pipeline for forecasting Mars surface conditions."""

import os

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


def get_device():
    """Return CUDA device if available, else CPU."""
    import torch

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
