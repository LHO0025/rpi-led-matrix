# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Raspberry Pi LED matrix control system: Flask backend (`backend/`) + React/TypeScript frontend (`frontend/`) + LED display driver (`backend/viewer.py`). Controls RGB LED matrix displays via a web GUI with authentication, image management, brightness/timing controls, and power management.

## Build & Run Commands

```bash
# Deploy everything (builds frontend, installs deps, sets up systemd service)
sudo ./scripts/deploy.sh

# Frontend development
cd frontend && npm install && npm run dev    # Dev server
cd frontend && npm run build                 # Production build
cd frontend && npx eslint .                  # Lint

# Python backend
pip install -r requirements.txt              # Install dependencies
python backend/server.py                     # Run Flask server (port 5000)
python backend/viewer.py                     # Run LED display driver

# System service management
sudo systemctl start|stop|restart|status led-matrix-system
sudo journalctl -u led-matrix-system -f      # View logs
```

No automated test suite exists.

## Architecture

```
Browser (React SPA) ──HTTP──▶ Flask API (backend/server.py:5000)
                                    │
                          ┌─────────┼──────────┐
                     Unix Socket    │     File I/O
                   /tmp/ledctl.sock │
                          │         │
              backend/viewer.py  config.ini, .auth,
                      │          order.json, matrix_images/
                   SPI/GPIO
                      │
                 RGB LED Matrix
```

**backend/config.py** — Shared path configuration used by both server and viewer. Resolves DATA_DIR (`/data/matrix` with fallback to project root), IMAGE_FOLDER, CONFIG_DIR, and validates writability at startup.

**backend/server.py** — Flask API handling auth (JWT), image CRUD, display control, overlay filesystem management. Communicates with viewer via Unix datagram socket (`/tmp/ledctl.sock`). Socket commands: `on`, `off`, `brightness:N`, `hold:N`, `reload`. No default password — first user must set one via the web UI.

**backend/viewer.py** — Lazy-loading image display engine: only decodes the currently-displayed image into memory (safe for Pi Zero W 2's 512MB RAM). Renders to LED matrix hardware via `rgbmatrix` library with fade transitions. Control thread has error recovery and auto-restarts on exceptions.

**frontend/src/App.tsx** — Single-component React app. Manages dual state: server state (source of truth) and local pending state (uncommitted changes). Upload errors are tracked per-file and surfaced to the user. ObjectURLs for pending previews are cached and revoked to prevent memory leaks.

## Project Structure

```
backend/          Python server, viewer, and shared config
frontend/         React/TypeScript web app (Vite)
scripts/          Deployment, start/stop, and setup scripts
docs/             DEPLOYMENT.md, OVERLAY_SETUP.md
matrix_images/    Image storage
```

## Key Conventions

- Frontend is built with Vite + React 19 + Tailwind CSS 4 + Radix UI components
- Auth uses Werkzeug password hashing + JWT tokens (24h expiry) stored in `.auth` file
- No default password — user sets one via web UI on first access
- Image uploads accept PNG, JPG, GIF, WebP (WebP auto-converted to PNG), max 4MB
- Thumbnails are cached in `matrix_images/.thumbs/` to avoid repeated PIL work on Pi
- Config stored in `config.ini` (brightness 1-100, hold_seconds 1-3600)
- Built frontend (`frontend/dist/`) is served by Flask as static files
- Viewer caps hardware brightness at 75 (MAX_BRIGHTNESS) to prevent overheating
- Frontend dev server URL configurable via `VITE_API_URL` env var (defaults to localhost:5000)
