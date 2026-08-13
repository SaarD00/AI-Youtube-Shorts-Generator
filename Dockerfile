# ffmpeg is the pipeline's core dependency, so the image ships it rather than
# relying on the host.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copied first so a code change does not invalidate the dependency layer.
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn

COPY . .

# Rendered videos land here; mount a volume over it to keep them across restarts.
RUN mkdir -p assets/final assets/temp assets/audio_clips assets/video_clips

# Runs as a non-root user, which also means the mounted volume must be writable
# by this uid (see docker-compose.yml).
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000

# One worker on purpose: the job state that tracks the running render lives in
# process memory, so a second worker would report "idle" while a render is going.
# Long timeout because a request returns only after the batch is handed off.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", \
     "--timeout", "120", "webapp:app"]
