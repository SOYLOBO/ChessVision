/**
 * ChessVision Signaling Server
 *
 * Adapted from VisionClaw signaling server (VisionClaw/samples/CameraAccess/server/index.js).
 * Preserves the original room-code pairing flow exactly:
 *   1. iOS/glasses app sends { type: "create" } → server generates 6-char room code
 *   2. Desktop/browser sends { type: "join", room: "ABCD12" } → server pairs them
 *   3. SDP offer/answer and ICE candidates are relayed between peers
 *   4. Creator can rejoin after backgrounding within 60s grace period
 *
 * What was reused from VisionClaw:
 *   - Room code generation (same charset, same 6-char length)
 *   - Room lifecycle (create/join/rejoin/destroy with grace period)
 *   - SDP + ICE relay logic (unchanged)
 *   - TURN credential endpoint (/api/turn)
 *   - WebSocket message protocol (all message types preserved)
 *
 * What was added for ChessMate:
 *   - Serves ChessVision web UI from ./public/
 *   - CORS headers for ChessMate backend calls from the viewer
 *   - Port defaults to 8090 (to avoid conflict with ChessMate services on 8001-8003)
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const { WebSocketServer } = require("ws");

const PORT = process.env.PORT || 8090;
const rooms = new Map(); // roomCode -> { creator: ws, viewer: ws, destroyTimer: timeout|null }

// Grace period (ms) before destroying a room when creator disconnects.
// Allows the iOS user to switch apps and come back.
// Reused from VisionClaw — 60 seconds.
const ROOM_GRACE_PERIOD_MS = 60_000;

// TURN: ExpressTURN (reused from VisionClaw signaling server)
const EXPRESSTURN_SERVER = process.env.EXPRESSTURN_SERVER || "free.expressturn.com";
const EXPRESSTURN_USER = process.env.EXPRESSTURN_USER || "efPU52K4SLOQ34W2QY";
const EXPRESSTURN_PASS = process.env.EXPRESSTURN_PASS || "1TJPNFxHKXrZfelz";

function getTurnCredentials() {
  return {
    iceServers: [
      {
        urls: [
          `turn:${EXPRESSTURN_SERVER}:3478`,
          `turn:${EXPRESSTURN_SERVER}:3478?transport=tcp`,
          `turn:${EXPRESSTURN_SERVER}:80`,
          `turn:${EXPRESSTURN_SERVER}:80?transport=tcp`,
          `turns:${EXPRESSTURN_SERVER}:443?transport=tcp`,
        ],
        username: EXPRESSTURN_USER,
        credential: EXPRESSTURN_PASS,
      },
    ],
  };
}

// Room code generation — identical to VisionClaw
// 6 characters, no ambiguous chars (0/O, 1/I/L)
function generateRoomCode() {
  const chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
  let code = "";
  for (let i = 0; i < 6; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return code;
}

// ── HTTP server ─────────────────────────────────────────────────────────────

const httpServer = http.createServer((req, res) => {
  // CORS for ChessMate backend calls
  if (req.method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    });
    res.end();
    return;
  }

  // TURN credentials API (reused from VisionClaw)
  if (req.url === "/api/turn") {
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    });
    res.end(JSON.stringify(getTurnCredentials()));
    return;
  }

  // Active rooms count (debug endpoint)
  if (req.url === "/api/rooms") {
    const roomList = [];
    for (const [code, room] of rooms) {
      roomList.push({
        code,
        hasCreator: !!(room.creator && room.creator.readyState === 1),
        hasViewer: !!(room.viewer && room.viewer.readyState === 1),
      });
    }
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    });
    res.end(JSON.stringify({ rooms: roomList, count: roomList.length }));
    return;
  }

  // Serve static files from ./public/
  let filePath = path.join(
    __dirname,
    "public",
    req.url === "/" ? "index.html" : req.url
  );

  const ext = path.extname(filePath);
  const contentTypes = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
  };

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }
    res.writeHead(200, {
      "Content-Type": contentTypes[ext] || "text/plain",
    });
    res.end(data);
  });
});

// ── WebSocket signaling ─────────────────────────────────────────────────────
// Protocol is identical to VisionClaw signaling server.
// Message types: create, join, rejoin, offer, answer, candidate
// Server relays SDP/ICE between creator and viewer by room code.

const wss = new WebSocketServer({ server: httpServer });

wss.on("connection", (ws, req) => {
  let currentRoom = null;
  let role = null; // 'creator' or 'viewer'
  const clientIP = req.headers["x-forwarded-for"] || req.socket.remoteAddress;
  console.log(`[WS] New connection from ${clientIP}`);

  ws.on("message", (data) => {
    let msg;
    try {
      msg = JSON.parse(data);
    } catch {
      return;
    }

    switch (msg.type) {
      // ── Room creation (iOS/glasses app) ──
      case "create": {
        const code = generateRoomCode();
        rooms.set(code, { creator: ws, viewer: null, destroyTimer: null });
        currentRoom = code;
        role = "creator";
        ws.send(JSON.stringify({ type: "room_created", room: code }));
        console.log(`[Room] Created: ${code}`);
        break;
      }

      // ── Creator reconnects after backgrounding ──
      case "rejoin": {
        const room = rooms.get(msg.room);
        if (!room) {
          ws.send(
            JSON.stringify({ type: "error", message: "Room not found" })
          );
          return;
        }
        if (room.destroyTimer) {
          clearTimeout(room.destroyTimer);
          room.destroyTimer = null;
          console.log(
            `[Room] Creator rejoined, cancelled destroy timer: ${msg.room}`
          );
        }
        room.creator = ws;
        currentRoom = msg.room;
        role = "creator";
        ws.send(JSON.stringify({ type: "room_rejoined", room: msg.room }));
        // If viewer is already waiting, trigger a new offer
        if (room.viewer && room.viewer.readyState === 1) {
          ws.send(JSON.stringify({ type: "peer_joined" }));
          console.log(
            `[Room] Viewer already present, notifying rejoined creator: ${msg.room}`
          );
        }
        console.log(`[Room] Creator rejoined: ${msg.room}`);
        break;
      }

      // ── Browser/desktop joins room by code ──
      case "join": {
        const room = rooms.get(msg.room);
        if (!room) {
          ws.send(
            JSON.stringify({ type: "error", message: "Room not found" })
          );
          return;
        }
        if (room.viewer) {
          ws.send(JSON.stringify({ type: "error", message: "Room is full" }));
          return;
        }
        room.viewer = ws;
        currentRoom = msg.room;
        role = "viewer";
        ws.send(JSON.stringify({ type: "room_joined" }));
        if (room.creator && room.creator.readyState === 1) {
          room.creator.send(JSON.stringify({ type: "peer_joined" }));
        }
        console.log(`[Room] Viewer joined: ${msg.room}`);
        break;
      }

      // ── SDP + ICE relay (unchanged from VisionClaw) ──
      case "offer":
      case "answer":
      case "candidate": {
        const room = rooms.get(currentRoom);
        if (!room) {
          console.log(
            `[Relay] ${msg.type} from ${role} but room ${currentRoom} not found`
          );
          return;
        }
        const target = role === "creator" ? room.viewer : room.creator;
        if (target && target.readyState === 1) {
          target.send(JSON.stringify(msg));
          console.log(
            `[Relay] ${msg.type} from ${role} -> ${role === "creator" ? "viewer" : "creator"} (room ${currentRoom})`
          );
        } else {
          console.log(
            `[Relay] ${msg.type} from ${role} but target not ready (room ${currentRoom})`
          );
        }
        break;
      }
    }
  });

  ws.on("error", (err) => {
    console.log(
      `[WS] Error for ${role} in room ${currentRoom}: ${err.message}`
    );
  });

  ws.on("close", (code, reason) => {
    console.log(
      `[WS] Closed: ${role} in room ${currentRoom} (code=${code}, reason=${reason || "none"})`
    );

    if (currentRoom && rooms.has(currentRoom)) {
      const room = rooms.get(currentRoom);
      const otherPeer = role === "creator" ? room.viewer : room.creator;
      if (otherPeer && otherPeer.readyState === 1) {
        otherPeer.send(JSON.stringify({ type: "peer_left" }));
      }
      if (role === "creator") {
        // Grace period — don't destroy immediately (VisionClaw pattern)
        room.creator = null;
        room.destroyTimer = setTimeout(() => {
          if (rooms.has(currentRoom)) {
            const r = rooms.get(currentRoom);
            if (!r.creator || r.creator.readyState !== 1) {
              if (r.viewer && r.viewer.readyState === 1) {
                r.viewer.send(
                  JSON.stringify({ type: "error", message: "Stream ended" })
                );
              }
              rooms.delete(currentRoom);
              console.log(
                `[Room] Destroyed after grace period: ${currentRoom}`
              );
            }
          }
        }, ROOM_GRACE_PERIOD_MS);
        console.log(
          `[Room] Creator disconnected, grace period started (${ROOM_GRACE_PERIOD_MS / 1000}s): ${currentRoom}`
        );
      } else {
        room.viewer = null;
      }
    }
  });
});

// ── Start ────────────────────────────────────────────────────────────────────

httpServer.listen(PORT, "0.0.0.0", () => {
  console.log(`ChessVision signaling server running on http://0.0.0.0:${PORT}`);
  console.log(`Web viewer available at http://localhost:${PORT}`);
  console.log(`TURN endpoint: http://localhost:${PORT}/api/turn`);
  console.log(`Active rooms: http://localhost:${PORT}/api/rooms`);
});
