# LLM Social Simulation

Multi-agent social simulation toolkit with:
- `open_resources` mode
- `open_world` mode
- Next.js replay/viewer frontend in `frontend/`

## Development Setup (uv)

We use **uv** for reproducible environments.

### 1) Install `uv`

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

### 2) Create env and install deps

From repo root:

```bash
uv venv --python 3.12
uv sync --group dev
```

### 3) Configure OpenRouter (only needed for LLM runs)

```bash
cp .env.example .env
```

Then set `OPENROUTER_API_KEY` in `.env`.

### 4) Run tests and lint

```bash
uv run pytest
uv run ruff check .
```

## Quick Commands

Run backend API:

```bash
uv run python -m llm_social_simulation.api.run_server --host 127.0.0.1 --port 8000
```

Try OpenRouter connectivity:

```bash
uv run python llm_social_simulation/models/tests/try_openrouter.py
```

Run frontend:

```bash
cd frontend
npm install
npm run dev
```

## Notes

- Python requirement is in `pyproject.toml`.
- Use `uv run ...` to keep commands inside the managed environment.
