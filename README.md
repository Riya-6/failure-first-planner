# Failure-First Live Music Event Planning Agent

An AI-powered event planning system that applies **failure-first reasoning** to live music events. Instead of planning for success, it assumes the event has already failed — surfaces every realistic failure mode, generates mitigations, and produces a robust production-ready plan.

Built with OpenAI GPT, FastAPI, and SQLite. Includes a full-stack frontend with real-time job polling.

---

## How It Works

```
Event Details + Contractors
          ↓
 Failure Simulation (AI) ← real-world data: weather, venue, artist risk
          ↓
 Mitigation Generation (AI)
          ↓
 Critical failures remain? → loop again (up to N iterations)
          ↓
 Final Robust Plan (AI)
          ↓
 Timeline · Risk Register · Go/No-Go Checkpoints · Backup Options
```

Three specialised AI agents run in a feedback loop:
1. **Failure Simulator** — identifies top failure scenarios across 8 categories
2. **Mitigation Agent** — generates preventive and reactive actions per failure
3. **Replanner** — produces the final structured plan with named contractors

---

## Tech Stack

- **AI** — OpenAI API (`gpt-4o-mini` default, configurable)
- **Backend** — Python 3.10+, FastAPI, SQLite
- **Frontend** — Vanilla HTML/CSS/JS with Tailwind CDN
- **Data Tools** — Open-Meteo (weather), Ticketmaster (venue), Setlist.fm (artist risk)
- **Testing** — pytest, pytest-asyncio

---

## Installation

### Prerequisites
- Python 3.10+
- OpenAI API key

### Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/failure-first-planner.git
cd failure-first-planner

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_MODEL` | No | Model to use (default: `gpt-4o-mini`) |
| `PLANNER_API_KEY` | No | API key for the HTTP service (default: auth disabled) |
| `MAX_LOOP_ITERATIONS` | No | Max failure-first iterations (default: `3`) |
| `TICKETMASTER_API_KEY` | No | Enables real venue + competing event data |
| `SETLISTFM_API_KEY` | No | Enables artist cancellation history |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

---

## Usage

### Option 1 — Web Interface (recommended)

```bash
.venv\Scripts\uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000` in your browser, fill in event details and contractor names, and click **Generate Plan**.

Interactive API docs available at `http://localhost:8000/docs`.

### Option 2 — CLI

```bash
# Run with built-in demo event
python run.py

# Run with your own event JSON
python run.py --event my_event.json

# Run with a multi-event file
python run.py --event events.json --key soundwave_outdoor --output out/plan.json
```

### Event JSON format

```json
{
  "name": "Neon Nights Festival 2026",
  "venue": "Stubb's Waller Creek Amphitheater",
  "venue_capacity": 2750,
  "headliner": "Hozier",
  "supporting_acts": ["Dermot Kennedy", "Orla Gartland"],
  "date": "2026-08-22",
  "is_outdoor": true,
  "expected_attendance": 2500,
  "budget_usd": 180000,
  "city": "Austin, TX",
  "backup_venue": "ACL Live at the Moody Theater",
  "sound_vendor": "Nomad Sound Austin",
  "stage_company": "Texas Stage Works",
  "security_company": "Contemporary Services Corp",
  "catering_vendor": "Austin Food Trailer Coalition",
  "medical_provider": "Austin Emergency Services LLC",
  "ticketing_platform": "Eventbrite",
  "production_manager": "Marcus Webb",
  "notes": "Curfew strictly 11pm per city permit."
}
```

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/plans/async` | Submit event, returns `job_id` immediately |
| `GET` | `/jobs/{job_id}` | Poll job status (`pending -> running -> done`) |
| `GET` | `/plans` | List all saved plans |
| `GET` | `/plans/{plan_id}` | Retrieve a specific plan |

All endpoints except `/health` require `X-API-Key` header (if `PLANNER_API_KEY` is set).

---

## Running Tests

```bash
# Unit tests (fast, no API calls)
pytest tests/unit/ -v

# Integration tests (hits real OpenAI API, costs tokens)
pytest tests/integration/ -v -m integration
```

---

## Project Structure

```
failure-first-planner/
├── src/
│   ├── agents/           # AI agents: failure_simulator, mitigation_agent, replanner
│   ├── api/              # FastAPI app with async job queue
│   ├── models/           # Pydantic data models: event, failure, plan
│   ├── orchestrator/     # Main failure-first loop
│   ├── prompts/          # All LLM prompt templates
│   ├── storage/          # SQLite persistence layer
│   ├── tools/            # External data: weather, venue, artist, ticketing, logistics
│   └── utils/            # Config, logging, retry, cost tracking
├── frontend/             # Single-page HTML frontend
├── tests/
│   ├── unit/             # Mocked tests (no API calls)
│   └── integration/      # Real API tests
├── assets/example_plans/ # Generated plans (JSON)
├── run.py                # CLI entry point
└── requirements.txt
```

---

## Output Plan Structure

Each generated plan includes:

- **Summary** — 2-3 sentence executive overview naming headliner, venue, and date
- **Timeline** — Ordered actions with named owner, deadline, and contingency
- **Go/No-Go Checkpoints** — Measurable pass/fail criteria with fallback actions
- **Risk Register** — All surfaced risks with severity, named owner, and mitigation
- **Backup Options** — Named backup venue, headliner, sound vendor, and generator

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and run the test suite: `pytest tests/unit/ -v`
4. Commit: `git commit -m "Add your feature"`
5. Push and open a pull request

Please keep all prompt templates in `src/prompts/failure_first.py` — never inline them in agent code.

---

