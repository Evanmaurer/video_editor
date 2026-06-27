# MontageAI

**AI-Powered Gaming Montage Editor**

MontageAI is a professional desktop application for creating AI-assisted gaming montages. Starting with Albion Online, it helps creators turn hundreds of raw gameplay clips into polished montages — with every AI decision transparent, scored, and fully editable.

## Status

**Milestone 1: Application Shell** — Complete (tag: `milestone-1`). Milestone 2 (Media Pipeline) is next.

See [Milestone 1 Summary](docs/milestone-1-summary.md) and [PROJECT_STATE.md](PROJECT_STATE.md) for details.

## Quick Start

```bash
./scripts/setup.sh   # Install Node + Python dependencies
pnpm dev             # Start Electron app + Python backend
```

**Requirements:** Node.js 22 LTS (see `.node-version`), Python 3.11+, pnpm 9+. FFmpeg is required starting in Milestone 2.

Optional: copy `.env.example` to `.env` to customize backend URL, auth token, or connect-only mode.

## Key Features (Planned)

- Import hundreds of gameplay clips and reference montages
- AI analysis: excitement scoring, Albion event detection (bombs, wipes, loot)
- Music analysis: BPM, beats, drops, energy curves
- Style learning from reference montages
- AI-generated **editable timelines** (not fixed renders)
- Natural language timeline editing via AI chat
- High-quality video export (H.264/H.265)

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Desktop | Electron |
| Frontend | React, TypeScript, TailwindCSS |
| Backend | Python, FastAPI |
| Database | SQLite |
| Video | FFmpeg, OpenCV, PyAV |
| AI | PyTorch, ONNX Runtime, Whisper, EasyOCR |

## Documentation

Complete design package in [`/docs`](docs/README.md):

- [Product Vision](docs/product-vision.md)
- [Product Requirements (PRD)](docs/01-prd.md)
- [Software Architecture](docs/02-software-architecture.md)
- [Development Roadmap](docs/15-development-roadmap.md)
- [Development Guide](docs/development-guide.md)
- [Milestone 1 Summary](docs/milestone-1-summary.md)
- [Project State](PROJECT_STATE.md)

## Project Structure

```
montage-ai/
├── apps/desktop/          # Electron + React frontend
├── apps/backend/          # Python FastAPI backend
├── packages/shared-types/ # Shared TypeScript types
├── ai/plugins/albion/     # Albion game plugin stub (M3+)
├── docs/                  # Design documentation
├── scripts/               # setup.sh, validate-electron-config.mjs
└── PROJECT_STATE.md       # Living project memory
```

## Development

```bash
pnpm test        # All frontend + backend tests (32 total)
pnpm typecheck   # TypeScript strict check
pnpm lint        # ESLint
```

See [Development Guide](docs/development-guide.md) for full setup, environment variables, and workflow.

## License

TBD
