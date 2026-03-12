# LLM Social Simulation Frontend (Open Resources Viewer)

Next.js + TypeScript + Tailwind + PixiJS replay viewer for the Open Resources simulation.

## Run

From repo root:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

To enable "Run Backend Simulation" from UI, start the Python run API in another terminal:

```bash
uv run python -m llm_social_simulation.api.run_server --host 127.0.0.1 --port 8000
```

If your API runs at another address, set:

```bash
NEXT_PUBLIC_SIM_API_BASE=http://127.0.0.1:8000
```

## Mock Replay Source

Default source is local JSON:

- `lib/mock/sampleReplay.json`

The page loads it through:

- `lib/replay/replaySource.ts` (`loadReplay({ mode: "mock" })`)

## Data Contract

Core types are in:

- `lib/replay/replayTypes.ts`

Main semantic objects:

- `SimulationReplay`
- `TickState`
- `AgentState`

## Swap Backend Data Later

The viewer is already separated from simulation logic. To switch source:

1. Keep backend as source of truth (Python engine).
2. Expose serialized ticks via HTTP or WebSocket.
3. Update `loadReplay` in `lib/replay/replaySource.ts`:
   - `mode: "http"` for batch replay payloads
   - `mode: "ws"` for live frame streaming
4. Use `lib/replay/replayAdapter.ts` if backend JSON shape differs from `TickState`.

## Backend Run Flow

UI now supports the full loop:

1. Configure run params in the left `Run Config` panel.
2. Click `Run Backend Simulation`.
3. Frontend calls:
   - `POST /api/runs`
   - `GET /api/runs/{run_id}` (poll)
   - `GET /api/runs/{run_id}/replay`
4. Replay auto-loads when status reaches `done`.

## Key UI Modules

- `components/pixi/*`: world rendering and animation layers
- `components/simulation/*`: toolbar, metrics, inspector, charts
- `lib/replay/useReplayController.ts`: playback state machine
