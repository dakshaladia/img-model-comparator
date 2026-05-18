# Sweep

Parameter exploration tool for generative image models. Pick a model, mark any input as swept, run variations in parallel, compare results in a labeled grid.

Supports 6 image models across 5 vendors. Forms are generated dynamically from each model's OpenAPI schema. Prompt sweep uses Claude Sonnet to expand a base prompt into stylistic variations along a named axis.

## Prerequisites

- Python 3.12+
- A [Replicate](https://replicate.com) API token (for image generation)
- An [Anthropic](https://console.anthropic.com) API key (for prompt expansion)

## Local setup

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd <repo-dir>

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and fill in:
#   REPLICATE_API_TOKEN=r8_...
#   ANTHROPIC_API_KEY=sk-ant-...

# 5. Start the dev server
python -m uvicorn main:app --reload
```

Open http://localhost:8000. The database (`data/sweep.db`) is created automatically on first startup.

## Running tests

```bash
# Full test suite (no external API calls, ~1 second)
pytest tests/ -v

# Ad-hoc integration tests (starts its own server)
python scripts/test_phase5.py              # no API calls
python scripts/test_phase5.py --with-claude # includes real Claude calls
python scripts/test_phase6.py --with-generation # includes real Replicate call (~$0.003)
```

## Docker

```bash
# Build
docker build -t sweep .

# Run (pass your API keys via .env file)
docker run --env-file .env -p 8000:8000 sweep
```

Open http://localhost:8000. The SQLite database lives at `/app/data/sweep.db` inside the container.

## Deploy to Fly.io

```bash
# 1. Install the Fly CLI if you haven't
# https://fly.io/docs/flyctl/install/

# 2. Authenticate
fly auth login

# 3. Launch the app (first time only)
fly launch --no-deploy

# 4. Create a persistent volume for SQLite (first time only)
fly volumes create sweep_data --size 1 --region ord

# 5. Set secrets
fly secrets set REPLICATE_API_TOKEN=r8_... ANTHROPIC_API_KEY=sk-ant-...

# 6. Deploy
fly deploy
```

The app will be available at `https://<app-name>.fly.dev`. The `fly.toml` mounts the volume at `/app/data` so the SQLite database and schema cache persist across deploys.

Subsequent deploys only need `fly deploy`.

[ Note: Currently its deployed at: https://sweep-playground.fly.dev/ ]

## Project structure

```
sweep/
├── main.py                     # FastAPI app, startup, router includes
├── config.py                   # Constants, model slugs, costs, directions
├── models.py                   # Pydantic types: ModelInput, SweepAxis, etc.
├── routes/
│   ├── pages.py                # GET /
│   ├── model_form.py           # GET /model-form?slug=X
│   ├── sweep.py                # POST /sweep, GET /cell/{id}
│   └── prompt.py               # POST /prompt-expand
├── services/
│   ├── storage.py              # SQLite DDL + CRUD helpers
│   ├── replicate_client.py     # Async Replicate SDK wrappers
│   ├── prompt_expander.py      # Claude prompt expansion
│   ├── schema.py               # OpenAPI schema parser
│   └── sweep_engine.py         # Fire-and-forget generation worker
├── templates/
│   ├── base.html               # Design system, fonts, CSS
│   ├── index.html              # Model dropdown + results area
│   └── partials/               # HTMX fragment responses
├── static/
│   └── sweep.js                # Sweep toggles, cost preview, UI helpers
├── tests/                      # pytest unit + e2e tests
├── scripts/                    # Ad-hoc integration test scripts
├── Dockerfile
├── fly.toml
└── approach.md                 # Design decisions and tradeoffs
```

## Supported models

| Model | Vendor | Cost/image |
|-------|--------|------------|
| Imagen 4 Fast | Google | ~$0.020 |
| Flux Schnell | Black Forest Labs | ~$0.003 |
| Flux 1.1 Pro | Black Forest Labs | ~$0.040 |
| Seedream 4 | ByteDance | ~$0.025 |
| Recraft v3 | Recraft | ~$0.040 |
| SD 3.5 Large | Stability AI | ~$0.065 |

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `REPLICATE_API_TOKEN` | Yes | Replicate API token for image generation |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for prompt expansion via Claude Sonnet |
