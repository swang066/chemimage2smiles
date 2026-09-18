# ChemImage2SMILES MVP

Upload a PNG/JPG reaction scheme, detect candidate molecule regions, run an interchangeable OCSR adapter, validate SMILES with RDKit, and export JSON/CSV. The included OpenCV detector is a heuristic for clean schemes; check every crop and structure before using results in a chemical database.

## Start (Python 3.10–3.12)

On Windows, run `./start.ps1` from the project directory. It creates a virtual environment, installs the base requirements, and starts the server. For manual setup:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn chemimage.app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The base install starts in **unavailable OCSR mode**: it detects crops but deliberately leaves SMILES blank. This makes detection and exports usable without silently inventing molecules.

## Enable MolScribe

MolScribe has a separate, relatively heavy PyTorch dependency stack. Install it in a compatible environment with `pip install MolScribe`, download an official checkpoint, then set:

```powershell
$env:OCSR_BACKEND = "molscribe"
$env:MOLSCRIBE_CHECKPOINT = "C:\path\to\swin_base_char_aux_1m.pth"
```

See the [official MolScribe repository](https://github.com/thomas0809/MolScribe) for checkpoint and installation guidance. A missing package/checkpoint is reported in `/api/health`; startup and crop detection still work. The adapter uses the documented `MolScribe(...).predict_image(..., return_confidence=True)` interface. To add another model, implement `predict(PIL.Image) -> Prediction` in `chemimage/ocsr.py` and select it in `make_backend`.

On Linux, `apt install osra` and `OCSR_BACKEND=osra` enable the lower-memory OSRA adapter. OSRA may return no structure for difficult crops and does not provide a calibrated confidence value in this integration; those fields remain blank instead of being guessed.

## Production deployment

The `Dockerfile` builds a Linux service with OSRA installed. `railway.json` selects that image and checks `/api/health`. The image runs one worker on the platform's `PORT`; attach a persistent volume mounted at `/data` if job results must survive restarts. `REQUIRE_OCSR=1` makes a missing recognizer fail startup instead of quietly serving empty SMILES. The current Railway custom domain `image2smiles.ai-spectra.cn` requires a DNS-only CNAME to `5u77jgo0.up.railway.app` in Cloudflare. MolScribe remains available as an adapter for a server with more memory.

## API

- `POST /api/analyze`: multipart `file` (PNG/JPG), optional `boxes` JSON (`[[x1,y1,x2,y2], ...]`) for correcting detection. Returns job ID and molecule records.
- `GET /api/jobs/{id}`: saved result.
- `GET /api/jobs/{id}/crops/{n}.png`: crop image.
- `GET /api/jobs/{id}/export.json` or `/export.csv`: bulk export.
- `GET /api/health`: backend status.

Coordinates are pixel bounds in the uploaded image. Confidence is the model's value if supplied; no artificial score is assigned. RDKit validity checks syntax and chemical sanitization, not whether the recognized structure matches the picture. Isomeric SMILES contains stereochemistry only when OCSR supplied it. Uploaded jobs stay under `data/jobs/` on the local machine. The upload limit is 15 MB and 6000 pixels on either side.

## Example and tests

`examples/reaction_scheme.jpg` is the image attached in the referenced conversation. It is used for a detection smoke test, not as verified ground truth; the earlier chat SMILES were unverified manual readings. Run `python -m pytest -q` after installing dependencies. Tests cover multiple-region detection, RDKit normalization, and the upload/export flow with a deterministic fake OCSR adapter.

PDF support can be added by rendering pages to images before `analyze_image`. The backend and per-page coordinate format are already separated from the upload handler.

