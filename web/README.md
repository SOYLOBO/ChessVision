# ChessVision

Live video source manager for ChessMate AI. Handles webcam, phone camera, and Meta glasses WebRTC streams — then feeds frames into the ChessMate vision → session → engine pipeline.

## Quick start

```bash
cd apps/chessvision
npm install
npm start
# Open http://localhost:8090
```

ChessMate backend services must be running (engine :8001, vision :8002, session :8003).

## Video sources

### 1. Webcam (no signaling needed)

Select **Webcam** → pick camera → **Connect**. Uses `getUserMedia` directly.

### 2. Phone / Meta Glasses (WebRTC with room-code pairing)

These sources use the VisionClaw room-code pairing flow:

1. **On the device** (iOS app / Meta glasses): start a stream → the app generates a 6-character room code and displays it
2. **In ChessVision**: select **Phone** or **Glasses** → enter the room code → **Connect**
3. The signaling server pairs the two peers, exchanges SDP offer/answer, negotiates ICE candidates
4. Once WebRTC connects, the remote video stream appears in ChessVision and frame sampling begins

#### Room code format

- 6 characters: `A-Z` (no O, I, L) + `2-9` (no 0, 1)
- Generated server-side when the device creates a room
- Single viewer per room
- 60-second grace period if the device app backgrounds

## How room-code pairing works

```
iOS/Glasses App              ChessVision Server              ChessVision Browser
     |                              |                              |
     |── create ──────────────────>|                              |
     |<── room_created (ABCD12) ──|                              |
     |                              |                              |
     | [user reads code aloud       |                   [user types ABCD12]
     |  or shares via message]      |                              |
     |                              |<──────── join (ABCD12) ──── |
     |                              |────────── room_joined ─────>|
     |<──── peer_joined ──────────|                              |
     |                              |                              |
     |── offer (SDP) ────────────>|── offer (SDP) ─────────────>|
     |                              |<──── answer (SDP) ──────── |
     |<── answer (SDP) ──────────|                              |
     |                              |                              |
     |── candidate ──────────────>|── candidate ───────────────>|
     |<── candidate ─────────────|<──── candidate ───────────── |
     |                              |                              |
     |========== WEBRTC P2P MEDIA STREAM ESTABLISHED ===========|
     |                              |                              |
     | video frames ──────────────────────────────────────────>  |
     |                              |       frame sampling begins  |
     |                              |       /scan-frame → session  |
     |                              |       → engine (on change)   |
```

## ChessMate pipeline integration

Once a video source is connected, ChessVision samples frames at a configurable interval (default 800ms) and runs the full pipeline:

1. **Capture** — canvas snapshot of current video frame → base64 JPEG
2. **Vision** — `POST /scan-frame` with `input_mode` matching source (`webcam`, `phone`, `meta_glasses`)
3. **Session** — `POST /sessions/{id}/update` with vision result
4. **Engine** — `POST /analyze-position` **only** when:
   - `legal: true`
   - `used_fallback: false`
   - `confidence >= 0.65`
   - FEN has changed since last analysis

## Pipeline stop conditions

The frame loop stops automatically on:
- Source disconnect (webcam track ended, WebRTC failed)
- Source change (selecting a different tab)
- 5 consecutive backend errors
- Session end (user clicks Disconnect)

## Architecture

```
apps/chessvision/
  server.js          — Node.js signaling server + static file server
  public/
    index.html       — ChessVision web UI (single-page app)
  package.json
  README.md
```

The signaling server runs on port 8090 by default. It handles:
- WebSocket signaling for room-code pairing (same protocol as VisionClaw)
- TURN credential endpoint (`/api/turn`)
- Serving the web UI

## What was reused vs rewritten

### Reused from VisionClaw (unchanged)

| Component | Source |
|---|---|
| Room code generation | `VisionClaw/samples/CameraAccess/server/index.js` — same charset, same 6-char length |
| Room lifecycle | create / join / rejoin / destroy with 60s grace period — identical |
| SDP + ICE relay | All signaling message types preserved (`offer`, `answer`, `candidate`, `peer_joined`, `peer_left`) |
| TURN credentials | Same ExpressTURN endpoint and fetch pattern |
| WebSocket protocol | Same JSON message format — iOS app connects without changes |
| Candidate buffering | Same `pendingCandidates` pattern for candidates arriving before `setRemoteDescription` |
| Peer connection setup | Same ICE server config, same `ontrack` / `onicecandidate` / `oniceconnectionstatechange` handlers |

### Rewritten for ChessVision

| Component | What changed |
|---|---|
| Web UI | New layout with sidebar controls, pipeline status, coach output, event log |
| Frame sampling | Added canvas-based capture → base64 JPEG at configurable interval |
| ChessMate integration | Vision → Session → Engine pipeline with re-analysis guards |
| Source selector | Unified webcam / phone / glasses tabs with conditional room-code input |
| Event logging | Structured log with categories: session, source, scan, board, FEN, fallback, engine, coach |
| Error handling | Consecutive error counter, auto-stop after 5 failures |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | 8090 | Server port |
| `EXPRESSTURN_SERVER` | free.expressturn.com | TURN server hostname |
| `EXPRESSTURN_USER` | (built-in) | TURN username |
| `EXPRESSTURN_PASS` | (built-in) | TURN password |

## iOS app configuration

The iOS VisionClaw app needs to point its signaling URL at this server. In `Secrets.swift`:

```swift
static let webrtcSignalingURL = "ws://YOUR_MAC_IP:8090"
```

Or if deployed to Fly.io / cloud:
```swift
static let webrtcSignalingURL = "wss://your-chessvision-server.fly.dev"
```
