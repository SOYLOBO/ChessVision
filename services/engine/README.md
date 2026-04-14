# ChessMate AI – engine-service

Stockfish UCI wrapper with template-based coaching output.  
Part of the `chessmate-ai` monorepo under `services/engine/`.

---

## What it does

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness check — returns engine subprocess status |
| `/analyze-position` | POST | Full position analysis with coaching text |

---

## Local setup

### Prerequisites

- Python 3.12+
- Stockfish installed and on `PATH` (or set `STOCKFISH_PATH`)

```bash
# macOS
brew install stockfish

# Ubuntu / Debian
sudo apt install stockfish

# Arch
sudo pacman -S stockfish
```

### Install & run

```bash
cd services/engine

# Create virtualenv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Optional: copy and edit env
cp ../../infrastructure/.env.example .env

# Run dev server
uvicorn app.main:app --reload --port 8001
```

Visit `http://localhost:8001/docs` for the auto-generated Swagger UI.

---

## Docker

```bash
# From services/engine/
docker build -t chessmate-engine .
docker run -p 8001:8001 chessmate-engine
```

Or via the root compose file:

```bash
# From chessmate-ai/
docker compose up engine
```

---

## API reference

### POST `/analyze-position`

**Request body**

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
  "mode": "casual",
  "skillLevel": 20,
  "depth": 15,
  "multiPv": 3
}
```

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `fen` | string | ✅ | — | Validated with python-chess |
| `mode` | enum | ❌ | `casual` | `casual` `study` `puzzle` `blunder_check` `opening` |
| `skillLevel` | int 0–20 | ❌ | `20` | Maps to Stockfish Skill Level |
| `depth` | int 1–30 | ❌ | `15` | Search depth |
| `multiPv` | int 1–5 | ❌ | `3` | Number of top moves returned |

**Response**

```json
{
  "bestMove": "e7e5",
  "evaluation": -0.2,
  "topMoves": [
    { "move": "e7e5", "score": -0.2, "pv": ["e7e5", "g1f3", "b8c6"] },
    { "move": "c7c5", "score": -0.3, "pv": ["c7c5", "g1f3", "d7d6"] },
    { "move": "e7e6", "score": -0.4, "pv": ["e7e6", "d2d4", "d7d5"] }
  ],
  "principalVariation": ["e7e5", "g1f3", "b8c6"],
  "coachText": "Best move: e5. Position is roughly equal (-0.2 pawns).",
  "speakText": "Try e5. The position is roughly equal."
}
```

### GET `/health`

```json
{ "status": "ok", "engine": "ok" }
```

---

## Coaching modes

| Mode | Behavior |
|---|---|
| `casual` | Best move + score label |
| `study` | Best move + top alternatives with scores |
| `puzzle` | Hints only — does not reveal the move |
| `blunder_check` | Evaluates current position quality, flags danger |
| `opening` | Best move + opening principles reminder |

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `STOCKFISH_PATH` | `/usr/games/stockfish` | Path to Stockfish binary |
| `DEFAULT_DEPTH` | `15` | Analysis depth when not specified |
| `DEFAULT_MULTI_PV` | `3` | Top moves count when not specified |
| `PORT` | `8001` | Uvicorn port (Docker only) |

---

## Project structure

```
services/engine/
├── app/
│   ├── main.py              # FastAPI app factory + lifespan
│   ├── core/
│   │   ├── config.py        # Pydantic settings
│   │   └── stockfish.py     # Persistent UCI subprocess
│   ├── models/
│   │   └── analysis.py      # Request / response models
│   ├── coaching/
│   │   └── templates.py     # Template-based coaching generator
│   └── routers/
│       ├── analysis.py      # POST /analyze-position
│       └── health.py        # GET /health
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## What's NOT here yet (by design)

- **Vision service** – board detection and FEN generation from camera feed
- **LLM coaching** – natural language explanations via Claude
- **Coach service** – orchestration layer above engine
- **Voice service** – STT / TTS integration
