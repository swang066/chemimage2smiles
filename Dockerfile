FROM python:3.10-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OCSR_BACKEND=osra \
    REQUIRE_OCSR=1 \
    CHEMIMAGE_DATA_DIR=/data/jobs \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends osra libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY chemimage ./chemimage
COPY static ./static
RUN mkdir -p /data/jobs && useradd -m appuser && chown -R appuser:appuser /data
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn chemimage.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

