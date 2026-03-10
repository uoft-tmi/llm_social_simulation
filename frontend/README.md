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

## Key UI Modules

- `components/pixi/*`: world rendering and animation layers
- `components/simulation/*`: toolbar, metrics, inspector, charts
- `lib/replay/useReplayController.ts`: playback state machine

