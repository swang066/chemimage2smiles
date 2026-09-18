import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image


@dataclass
class Prediction:
    smiles: str | None
    confidence: float | None = None
    error: str | None = None


class Backend(Protocol):
    name: str
    status: str

    def predict(self, crop: Image.Image) -> Prediction: ...


class UnavailableBackend:
    name = "unavailable"

    def __init__(self, reason: str = "Set OCSR_BACKEND=molscribe and MOLSCRIBE_CHECKPOINT to enable recognition"):
        self.status = reason

    def predict(self, crop: Image.Image) -> Prediction:
        return Prediction(None, error=self.status)


class MolScribeBackend:
    name = "molscribe"
    status = "ready"

    def __init__(self, checkpoint: str):
        if not Path(checkpoint).is_file():
            raise FileNotFoundError(f"MolScribe checkpoint not found: {checkpoint}")
        import torch
        from molscribe import MolScribe

        self.model = MolScribe(checkpoint, device=torch.device("cuda" if torch.cuda.is_available() else "cpu"))

    def predict(self, crop: Image.Image) -> Prediction:
        try:
            output = self.model.predict_image(np.asarray(crop.convert("RGB")), return_confidence=True)
            value = output.get("confidence")
            if isinstance(value, (int, float)):
                confidence = float(value)
                confidence = confidence if 0 <= confidence <= 1 else None
            else:
                confidence = None
            return Prediction(output.get("smiles") or None, confidence)
        except Exception as exc:
            return Prediction(None, error=f"MolScribe inference failed: {exc}")


def make_backend() -> Backend:
    choice = os.getenv("OCSR_BACKEND", "unavailable").lower()
    if choice != "molscribe":
        if os.getenv("REQUIRE_OCSR") == "1":
            raise RuntimeError("OCSR is required but OCSR_BACKEND is not molscribe")
        return UnavailableBackend()
    try:
        return MolScribeBackend(os.getenv("MOLSCRIBE_CHECKPOINT", ""))
    except Exception as exc:
        if os.getenv("REQUIRE_OCSR") == "1":
            raise RuntimeError(f"MolScribe failed to initialize: {exc}") from exc
        return UnavailableBackend(f"MolScribe unavailable: {exc}")