import csv
import io
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from .chemistry import validate_smiles
from .detection import detect_regions, validate_boxes
from .ocsr import make_backend

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("CHEMIMAGE_DATA_DIR", ROOT / "data" / "jobs"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="ChemImage2SMILES MVP")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
backend = make_backend()


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"backend": backend.name, "status": backend.status}


def job_path(job_id: str) -> Path:
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID")
    path = DATA_DIR / job_id
    if not path.is_dir():
        raise HTTPException(404, "Job not found")
    return path


def analyze_image(image: Image.Image, boxes: list[list[int]], job_id: str) -> dict:
    path = DATA_DIR / job_id
    path.mkdir(parents=True, exist_ok=False)
    image.save(path / "source.png")
    records = []
    for index, box in enumerate(boxes, 1):
        crop = image.crop(tuple(box))
        crop.save(path / f"crop_{index}.png")
        prediction = backend.predict(crop)
        record = {
            "id": index,
            "bbox": box,
            "crop": f"/api/jobs/{job_id}/crops/{index}.png",
            "confidence": prediction.confidence,
            "ocr_backend": backend.name,
            **validate_smiles(prediction.smiles),
        }
        record["validation"]["ocr_error"] = prediction.error
        records.append(record)
    result = {"job_id": job_id, "image_size": list(image.size), "backend": backend.name, "backend_status": backend.status, "molecules": records}
    (path / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), boxes: str | None = Form(None)):
    contents = await file.read(15 * 1024 * 1024 + 1)
    if len(contents) > 15 * 1024 * 1024:
        raise HTTPException(413, "Image exceeds 15 MB")
    try:
        source = Image.open(io.BytesIO(contents))
        if source.format not in {"PNG", "JPEG"}:
            raise HTTPException(415, "Upload PNG or JPEG")
        if max(source.size) > 6000:
            raise HTTPException(413, "Image dimensions exceed 6000 pixels")
        image = source.convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Invalid image")
    try:
        regions = validate_boxes(json.loads(boxes), image.size) if boxes else detect_regions(image)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"Invalid boxes: {exc}")
    return analyze_image(image, regions, str(uuid.uuid4()))


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return json.loads((job_path(job_id) / "result.json").read_text(encoding="utf-8"))


@app.get("/api/jobs/{job_id}/crops/{index}.png")
def get_crop(job_id: str, index: int):
    path = job_path(job_id) / f"crop_{index}.png"
    if index < 1 or not path.is_file():
        raise HTTPException(404, "Crop not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/jobs/{job_id}/export.json")
def export_json(job_id: str):
    return FileResponse(job_path(job_id) / "result.json", media_type="application/json", filename=f"{job_id}.json")


@app.get("/api/jobs/{job_id}/export.csv")
def export_csv(job_id: str):
    data = get_job(job_id)
    stream = io.StringIO()
    fields = ["id", "bbox", "crop", "raw_smiles", "canonical_smiles", "isomeric_smiles", "formula", "confidence", "ocr_backend", "rdkit_valid", "valence_valid", "stereochemistry", "error", "ocr_error"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for molecule in data["molecules"]:
        row = {key: molecule.get(key) for key in fields}
        row["bbox"] = json.dumps(row["bbox"])
        row.update(molecule["validation"])
        writer.writerow(row)
    return Response(stream.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{job_id}.csv"'})