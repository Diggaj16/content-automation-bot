# Official Playwright Python image — Chromium + all Linux browser dependencies included.
# Version pinned to match installed playwright==1.60.0.
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

# ── Python dependencies ────────────────────────────────────────────────────
# Copy only pyproject.toml first so this layer is cached until deps change.
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "."

# ── Playwright browsers ────────────────────────────────────────────────────
# Install bundled Chromium for Linux (NOT msedge — that's Windows only).
# The base image already has system-level browser deps; this just fetches the binary.
RUN playwright install chromium

# ── Application code ───────────────────────────────────────────────────────
COPY . .

# ── Runtime defaults ───────────────────────────────────────────────────────
# PLAYWRIGHT_BROWSER_CHANNEL is intentionally NOT set here.
# Leaving it empty means Playwright uses its bundled Chromium automatically.
# On Windows dev machines, set PLAYWRIGHT_BROWSER_CHANNEL=msedge in backend/.env.

EXPOSE 8000

# Default: FastAPI server.
# The worker service overrides this with the arq command (see docker-compose.yml).
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
