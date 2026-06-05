# Official Playwright Python image — Chromium + all Linux browser dependencies included.
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

# ── System deps ────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────────────
# Copy requirements first so this layer is cached until requirements.txt changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ── Playwright browsers ────────────────────────────────────────────────────
# Install bundled Chromium for Linux (not msedge — that's Windows only).
RUN playwright install chromium

# ── Application code ───────────────────────────────────────────────────────
COPY . .

EXPOSE 8000

# Default: FastAPI server.
# Worker service overrides this with the arq command (see docker-compose.yml).
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
