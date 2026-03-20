"""Export trained LSTM models to ONNX format for inference without PyTorch."""

import json
import os

import torch

from . import MODEL_DIR
from .model import LSTMPredictor


def export_model(horizon: int, model_dir: str = MODEL_DIR) -> str:
    """Export a trained LSTM model to ONNX format.

    Args:
        horizon: Prediction horizon (1, 7, or 30)
        model_dir: Directory containing trained model artifacts

    Returns:
        Path to the exported ONNX file
    """
    meta_path = os.path.join(model_dir, f"lstm_h{horizon}_meta.json")
    with open(meta_path) as f:
        meta = json.load(f)

    model = LSTMPredictor(
        input_size=meta["input_size"],
        hidden_size=meta["hidden_size"],
        num_layers=meta["num_layers"],
        output_size=meta["output_size"],
    )
    model.load_state_dict(torch.load(
        os.path.join(model_dir, f"lstm_h{horizon}.pt"),
        weights_only=True,
        map_location="cpu",
    ))
    model.eval()

    seq_len = meta["seq_len"]
    input_size = meta["input_size"]
    dummy_input = torch.randn(1, seq_len, input_size)

    onnx_path = os.path.join(model_dir, f"lstm_h{horizon}.onnx")
    torch.onnx.export(
        model,
        (dummy_input,),
        onnx_path,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "output": {0: "batch_size"},
        },
        opset_version=17,
    )

    print(f"Exported h={horizon} model to {onnx_path}")
    return onnx_path


def export_all(model_dir: str = MODEL_DIR) -> list[str]:
    """Export all trained LSTM models (h=1, h=7, h=30) to ONNX format."""
    paths = []
    for horizon in (1, 7, 30):
        path = export_model(horizon, model_dir)
        paths.append(path)
    return paths


if __name__ == "__main__":
    print("Exporting LSTM models to ONNX format")
    print("=" * 50)
    export_all()
    print("\nDone.")
