# ChessVision

Real-time chess position analysis using computer vision, Stockfish, and WebRTC streaming.

## Architecture

```
web/          → Node.js signaling server + web viewer (port 8090)
ios/          → SwiftUI iOS app (iPhone/Meta glasses camera capture)
services/
  engine/     → Stockfish UCI wrapper + coaching (port 8001)
  vision/     → 8-stage CV pipeline: board detection → FEN (port 8002)
  session/    → Session state management (port 8003)
```

## Quick Start

### Backend services (Docker)

```bash
docker compose up --build
```

This starts the engine (8001), vision (8002), and session (8003) services.

### Web viewer

```bash
cd web
npm install
npm start
# Open http://localhost:8090
```

### iOS app

1. Open `ios/CameraAccess.xcodeproj` in Xcode
2. Copy `CameraAccess/Secrets.swift.example` to `CameraAccess/Secrets.swift`
3. Add your Gemini API key
4. Build and run on your iPhone

## How It Works

1. **Capture** — iPhone or webcam streams a live view of a chess board via WebRTC
2. **Detect** — Vision service runs an 8-stage pipeline to extract a FEN position
3. **Analyze** — Engine service evaluates the position with Stockfish
4. **Coach** — Coaching templates generate natural-language move suggestions
