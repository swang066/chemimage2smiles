FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OCSR_BACKEND=molscribe \
    REQUIRE_OCSR=1 \
    MOLSCRIBE_CHECKPOINT=/app/models/swin_base_char_aux_1m.pth \
    CHEMIMAGE_DATA_DIR=/data/jobs \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch==1.13.1+cpu torchvision==0.14.1+cpu --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt MolScribe huggingface_hub
RUN mkdir -p /app/models && python -c "from huggingface_hub import hf_hub_download; hf_hub_download('yujieq/MolScribe', 'swin_base_char_aux_1m.pth', local_dir='/app/models')"
COPY chemimage ./chemimage
COPY static ./static
RUN mkdir -p /data/jobs && useradd -m appuser && chown -R appuser:appuser /data
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn chemimage.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]