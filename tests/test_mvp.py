import io
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from chemimage import app as module
from chemimage.chemistry import validate_smiles
from chemimage.detection import detect_regions
from chemimage.ocsr import OsraBackend, Prediction
from chemimage.ocsr import make_backend
import pytest


class FakeBackend:
    name = "fake"
    status = "ready"

    def predict(self, crop):
        return Prediction("C[C@H](O)F", 0.75)


def test_rdkit_normalization_and_invalid():
    good = validate_smiles("C[C@H](O)F")
    assert good["validation"]["rdkit_valid"] is True
    assert good["validation"]["stereochemistry"] == "assigned"
    assert good["formula"] == "C2H5FO"
    assert "@" in good["isomeric_smiles"]
    bad = validate_smiles("C1QQ")
    assert bad["validation"]["rdkit_valid"] is False
    assert bad["canonical_smiles"] is None


def test_detector_finds_two_separate_drawings():
    image = Image.new("RGB", (600, 260), "white")
    draw = ImageDraw.Draw(image)
    for x in (70, 340):
        draw.polygon([(x+40, 30), (x+95, 60), (x+95, 130), (x+40, 160), (x, 130), (x, 60)], outline="black", width=4)
        draw.line([(x+40, 30), (x+40, 160)], fill="black", width=3)
    boxes = detect_regions(image)
    assert len(boxes) == 2
    assert boxes[0][2] < boxes[1][0]


def test_upload_crop_and_exports(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(module, "backend", FakeBackend())
    client = TestClient(module.app)
    image = Image.new("RGB", (100, 100), "white")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    response = client.post("/api/analyze", files={"file": ("example.png", buffer.getvalue(), "image/png")}, data={"boxes": "[[10,10,90,90]]"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["molecules"]) == 1
    assert data["molecules"][0]["formula"] == "C2H5FO"
    assert data["molecules"][0]["confidence"] == 0.75
    job = data["job_id"]
    assert client.get(f"/api/jobs/{job}/crops/1.png").status_code == 200
    assert client.get(f"/api/jobs/{job}/export.json").json()["molecules"][0]["raw_smiles"] == "C[C@H](O)F"
    csv_text = client.get(f"/api/jobs/{job}/export.csv").text
    assert "C2H5FO" in csv_text and "raw_smiles" in csv_text


def test_reference_image_detects_multiple_regions():
    path = Path(__file__).resolve().parent.parent / "examples" / "reaction_scheme.jpg"
    with Image.open(path) as image:
        assert len(detect_regions(image)) >= 3


def test_required_ocsr_fails_closed(monkeypatch):
    monkeypatch.setenv("REQUIRE_OCSR", "1")
    monkeypatch.setenv("OCSR_BACKEND", "molscribe")
    monkeypatch.setenv("MOLSCRIBE_CHECKPOINT", "missing.pth")
    with pytest.raises(RuntimeError, match="MolScribe failed to initialize"):
        make_backend()


def test_osra_adapter_returns_recognized_smiles(monkeypatch):
    monkeypatch.setattr("chemimage.ocsr.shutil.which", lambda name: "/usr/bin/osra")
    monkeypatch.setattr(
        "chemimage.ocsr.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "CCO\n", ""),
    )
    result = OsraBackend().predict(Image.new("RGB", (50, 50), "white"))
    assert result.smiles == "CCO"
    assert result.confidence is None

