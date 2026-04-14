# ──────────────────────────────────────────────────────────────
# ChessMate AI – engine-service Dockerfile
# ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# System deps: Stockfish
RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /service

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY app/ ./app/

# ──────────────────────────────────────────────────────────────
# Runtime
# ──────────────────────────────────────────────────────────────
ENV STOCKFISH_PATH=/usr/games/stockfish \
    DEFAULT_DEPTH=15 \
    DEFAULT_MULTI_PV=3 \
    PORT=8001

EXPOSE 8001

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
