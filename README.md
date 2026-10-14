<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

**Marketing Campaign Audience Simulation Engine**
</br>
<em>Simulate how consumer segments react to campaigns before you launch</em>

[![GitHub Stars](https://img.shields.io/github/stars/TheRedSnail/SimSend?style=flat-square&color=DAA520)](https://github.com/TheRedSnail/SimSend/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/TheRedSnail/SimSend?style=flat-square)](https://github.com/TheRedSnail/SimSend/network)
[![Docker](https://img.shields.io/badge/Docker-GHCR-2496ED?style=flat-square&logo=docker&logoColor=white)](https://github.com/TheRedSnail/SimSend/pkgs/container/mirofish)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square)](./LICENSE)

</div>

---

## Overview

**MiroFish** is a multi-agent simulation engine that predicts how real-world audiences will react to marketing campaigns. Upload market research documents, describe your campaign, and MiroFish automatically:

1. Extracts consumer segments, brands, and market actors from your documents
2. Generates thousands of AI agents with realistic consumer personas
3. Simulates their interactions across social platforms over a 7-day campaign window
4. Produces a detailed **Campaign Effectiveness Prediction Report**

> **Input:** Market research PDFs + a campaign brief in natural language
> **Output:** A prediction report with audience reaction analysis, sentiment trajectories, and strategic recommendations — plus a live simulation world you can query

## How It Works

MiroFish builds a parallel digital market where AI agents — representing consumer segments, influencers, brands, and media — interact freely. By observing emergent group behavior, it surfaces insights that traditional surveys and focus groups miss.

### 5-Step Workflow

| Step | Name | What Happens |
|------|------|-------------|
| 1 | **Graph Build** | Analyzes uploaded documents to extract a market ontology (consumer types, brands, relationships) and builds a knowledge graph via Zep Cloud |
| 2 | **Environment Setup** | Generates agent personas with consumer behavior traits (purchase preferences, price sensitivity, brand affinity, media habits) and configures simulation parameters |
| 3 | **Simulation** | Runs dual-platform parallel simulation (Twitter + Reddit style) with agents posting, commenting, sharing, and reacting to campaign content |
| 4 | **Report Generation** | A ReACT-based Report Agent queries the simulation data with specialized tools and writes a structured Campaign Effectiveness Prediction Report |
| 5 | **Deep Interaction** | Chat with any individual agent or the Report Agent to explore specific consumer reactions and drill into findings |

### Entity Types

MiroFish generates 10 entity types per simulation, tailored to your market. Typical types include:

**Consumer segments:** YoungConsumer, PriceSensitiveShopper, BrandLoyalist, EarlyAdopter, PremiumBuyer, ParentConsumer

**Market actors:** Influencer, IndustryAnalyst, CompetitorBrand, RetailChannel, MarketingAgency, IndustryPress

**Fallbacks:** Person, Organization (catch-all types for entities that don't fit specific categories)

## Architecture

```
MiroFish/
├── backend/
│   ├── app/
│   │   ├── api/              # REST endpoints (graph, simulation, report)
│   │   ├── services/
│   │   │   ├── ontology_generator.py        # LLM-driven market ontology design
│   │   │   ├── graph_builder.py             # Zep Cloud knowledge graph construction
│   │   │   ├── oasis_profile_generator.py   # Consumer agent persona generation
│   │   │   ├── simulation_config_generator.py  # LLM-driven simulation parameters
│   │   │   ├── simulation_runner.py         # OASIS platform orchestration
│   │   │   ├── report_agent.py              # ReACT report generation + chat
│   │   │   └── zep_*.py                     # Zep Cloud integrations
│   │   └── utils/             # LLM client, file parsing, logging
│   └── scripts/               # Simulation execution scripts
├── frontend/
│   └── src/
│       ├── components/        # Step1-Step5 workflow components + GraphPanel
│       └── views/             # Home, Process, Report, Interaction views
└── docker-compose.yml
```

**Key dependencies:**
- [OASIS](https://github.com/camel-ai/oasis) — Multi-agent social simulation platform
- [Zep Cloud](https://www.getzep.com/) — Knowledge graph storage, entity memory, and graph search
- Any OpenAI-compatible LLM API — Powers ontology design, persona generation, simulation config, and report writing

## Quick Start

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| **Node.js** | 20.19+ or 22.12+ | `node -v` |
| **Python** | 3.11 - 3.12 | `python --version` |
| **uv** | Latest | `uv --version` |

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# LLM API (any OpenAI SDK-compatible endpoint)
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o

# Zep Cloud (free tier works for basic usage)
# Sign up at https://app.getzep.com/
ZEP_API_KEY=your_zep_api_key
```

### 2. Install Dependencies

```bash
# Install everything (Node + Python)
npm run setup:all
```

Or step by step:

```bash
npm run setup           # Node dependencies (root + frontend)
npm run setup:backend   # Python dependencies (auto-creates virtualenv)
```

### 3. Start

```bash
npm run dev
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

Ports already in use? Set `FRONTEND_PORT` and/or `FLASK_PORT` in `.env` — the dev server, its `/api` proxy, and docker-compose all follow them.

Start individually:

```bash
npm run backend    # Backend only
npm run frontend   # Frontend only
```

Both dev servers listen on `localhost` only. To reach them from another machine, set `FLASK_HOST=0.0.0.0` / `FRONTEND_HOST=0.0.0.0` — and set `ADMIN_API_KEY`, since the API has no user accounts.

### Production (no dev servers)

```bash
npm start    # builds the frontend, then serves UI + API with waitress on http://localhost:5001
```

### Docker

```bash
cp .env.example .env    # Configure API keys
docker compose up -d    # UI + API on http://localhost:5001
```

The image builds the frontend and serves it from the backend with waitress, runs as a non-root user (uid 1000), and persists `backend/uploads` and `backend/logs`. The port is published on `127.0.0.1` only; set `BIND_ADDRESS=0.0.0.0` to expose it (put it behind a reverse proxy and set `ADMIN_API_KEY`). On Linux, make sure the mounted `backend/uploads` and `backend/logs` directories are writable by uid 1000.

### Landing page and early-access sign-ups

`/welcome` is a scroll-driven landing page that walks through a sample run (documents → knowledge graph → conversations → report → follow-up questions) and ends with an early-access form. The app itself stays at `/`.

Sign-ups are saved to `backend/uploads/signups.json`, one record per email address. To read them, set `ADMIN_API_KEY` and call:

```bash
curl -H "X-Admin-Key: $ADMIN_API_KEY" http://localhost:5001/api/signup/list              # JSON
curl -H "X-Admin-Key: $ADMIN_API_KEY" "http://localhost:5001/api/signup/list?format=csv"  # CSV
```

The sample run on the landing page is illustrative content (`frontend/src/components/landing/story.js`); replace it with a recorded run before relying on it.

### Tests

```bash
npm test     # backend pytest + frontend vitest
npm run lint # frontend ESLint
```

## Usage

1. **Open** `http://localhost:3000` (dev) or `http://localhost:5001` (`npm start` / Docker)
2. **Upload** one or more market research documents (PDF, Markdown, TXT)
3. **Describe** your campaign brief — e.g., *"Simulate consumer reactions to a new eco-friendly packaging launch for our premium skincare line targeting young urban professionals"*
4. **Click** "Launch Simulation Engine" and follow the 5-step workflow
5. **Review** the generated Campaign Effectiveness Prediction Report
6. **Interact** — ask follow-up questions to the Report Agent or interview individual consumer agents

### Tips

- Start with **10-20 simulation rounds** for a quick preview before running longer simulations
- The simulation runs over a **7-day virtual timeline** with realistic consumer browsing patterns (evening peaks, lunch-hour browsing spikes)
- Higher-capability LLMs produce more nuanced agent personas and better reports

## Report Output

The Campaign Effectiveness Prediction Report typically includes:

- **Audience Reaction Overview** — How different consumer segments responded
- **Segment Analysis** — Deep dive into each consumer type's behavior
- **Sentiment & Word-of-Mouth** — Organic discussion patterns and sentiment trajectory
- **Competitive Impact** — How competitor brands and market actors reacted
- **Strategic Recommendations** — Data-backed suggestions for campaign optimization

## License

[AGPL-3.0](./LICENSE)

## Acknowledgments

MiroFish's simulation engine is powered by **[OASIS](https://github.com/camel-ai/oasis)** from the CAMEL-AI team.

Originally created by the [MiroFish team](https://github.com/666ghj/MiroFish) with strategic support from Shanda Group. This fork adapts the engine for marketing campaign audience simulation.
