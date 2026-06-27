# MontageAI

**AI-Powered Gaming Montage Editor**

MontageAI is a professional desktop application for creating AI-assisted gaming montages. Starting with Albion Online, it helps creators turn hundreds of raw gameplay clips into polished montages — with every AI decision transparent, scored, and fully editable.

## Status

**Milestone 0: Design Package** — Complete, awaiting approval before implementation begins.

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
- [Project State](PROJECT_STATE.md)

## Project Structure (Planned)

```
montage-ai/
├── apps/desktop/          # Electron + React frontend
├── apps/backend/          # Python FastAPI backend
├── packages/shared-types/ # Shared TypeScript + Python types
├── ai/                    # AI agents and game plugins
├── docs/                  # Design documentation
├── scripts/               # Setup and build scripts
└── tests/                 # E2E and integration tests
```

## Development

Implementation begins after Milestone 0 approval. See [Development Guide](docs/development-guide.md) for setup instructions.

## License

TBD
